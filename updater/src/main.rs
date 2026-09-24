//! EER Updater - 独立更新器程序
//!
//! 更新流程由 Python 侧 `installer.py` 生成 `_plan.json` 后启动本程序执行。
//! 为支持更新器自更新，Python 侧会优先运行更新包中的新版 `eer_updater.exe`，
//! 再由新版更新器替换安装目录中的旧文件。
//!
//! 安全边界：
//! - 所有计划路径必须是安装目录或解压目录下的相对路径。
//! - 删除和覆盖前先移动到 `_backup`，复制失败时尽量回滚。
//! - 主程序退出后才开始替换文件，避免 Windows 文件锁导致更新失败。

use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::collections::{HashMap, HashSet};
use std::env;
use std::fs;
use std::io::{self, Read, Write};
use std::path::{Component, Path, PathBuf};
use std::process::Command;

#[cfg(windows)]
use std::os::windows::fs::MetadataExt;
#[cfg(windows)]
use std::os::windows::process::CommandExt;

#[cfg(windows)]
use windows_sys::Win32::Foundation::{CloseHandle, INVALID_HANDLE_VALUE};
#[cfg(windows)]
use windows_sys::Win32::System::Threading::{
    OpenProcess, PROCESS_SYNCHRONIZE, WaitForSingleObject,
};

// ---------------------------------------------------------------------------
// 常量
// ---------------------------------------------------------------------------

const MAX_LOG_SIZE: u64 = 4 * 1024 * 1024; // 4MB
#[cfg(windows)]
const PARENT_WAIT_TIMEOUT_MS: u32 = 100;
const BACKUP_DIR_PREFIX: &str = "_update_backup_";
#[cfg(windows)]
const CREATE_NO_WINDOW_FLAG: u32 = 0x08000000;
#[cfg(windows)]
const FILE_ATTRIBUTE_REPARSE_POINT: u32 = 0x400;

// ---------------------------------------------------------------------------
// 更新计划 Plan JSON 结构
// ---------------------------------------------------------------------------

#[derive(Deserialize)]
struct UpdatePlan {
    /// 计划来源，仅用于日志和排查；新增来源必须保持向后兼容。
    #[serde(default)]
    package_type: String,
    /// 安装目录中需要删除或替换的旧文件/目录。
    #[serde(default)]
    remove_list: Vec<String>,
    /// 更新包中必须复制到安装目录的文件。
    #[serde(default)]
    copy_list: Vec<String>,
    /// 复制文件的 SHA-256 映射；旧 plan 可缺省，保持兼容。
    #[serde(default)]
    copy_hashes: HashMap<String, String>,
    /// 需要保留的用户数据路径；目录条目以 `/` 或 `\` 结尾。
    #[serde(default)]
    protected_list: Vec<String>,
}

// ---------------------------------------------------------------------------
// 日志
// ---------------------------------------------------------------------------

struct Logger {
    file: Option<fs::File>,
}

impl Logger {
    /// 初始化更新器日志文件，并在日志过大时轮转为备份文件。
    fn init(log_path: &Path) -> Self {
        // 轮转：如果日志超过 4MB，重命名为 .bak
        if log_path.exists()
            && let Ok(meta) = fs::metadata(log_path)
            && meta.len() > MAX_LOG_SIZE
        {
            let bak = log_path.with_extension("log.bak");
            let _ = fs::rename(log_path, &bak);
        }
        let file = fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(log_path)
            .ok();
        Logger { file }
    }

    /// 同时向控制台和日志文件写入一行带时间戳的消息。
    fn log(&mut self, msg: &str) {
        let ts = chrono_free_timestamp();
        let line = format!("[{ts}] {msg}\n");
        eprint!("{line}");
        if let Some(ref mut f) = self.file {
            let _ = f.write_all(line.as_bytes());
        }
    }
}

/// 返回 YYYY-MM-DD HH:MM:SS 格式的时间戳（不依赖 chrono crate）。
fn chrono_free_timestamp() -> String {
    use std::time::SystemTime;
    let dur = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .unwrap_or_default();
    let secs = dur.as_secs();
    // 简单转换为 UTC+8（北京时间）
    let secs = secs + 8 * 3600;
    let days = secs / 86400;
    let time_of_day = secs % 86400;
    let h = time_of_day / 3600;
    let m = (time_of_day % 3600) / 60;
    let s = time_of_day % 60;

    // 简化的日期计算（从 Unix epoch 开始）
    let (y, mo, d) = days_to_ymd(days as u32);
    format!("{y:04}-{mo:02}-{d:02} {h:02}:{m:02}:{s:02}")
}

/// 将 Unix epoch 后的天数转换为公历年月日。
fn days_to_ymd(mut days: u32) -> (u32, u32, u32) {
    days += 719468;
    let era = days / 146097;
    let doe = days - era * 146097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let mo = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if mo <= 2 { y + 1 } else { y };
    (y, mo, d)
}

// ---------------------------------------------------------------------------
// 路径安全
// ---------------------------------------------------------------------------

/// 检查路径是否为盘符根目录（如 C:\、D:\）。
fn is_drive_root_directory(path: &Path) -> bool {
    let s = path.to_string_lossy();
    let normalized = s.trim_end_matches('\\').trim_end_matches('/');
    // 格式：X:（单字母盘符 + 冒号）
    if normalized.len() == 2 {
        let bytes = normalized.as_bytes();
        (bytes[0].is_ascii_alphabetic()) && bytes[1] == b':'
    } else {
        false
    }
}

/// 在根目录下解析相对路径，防止路径穿越。
///
/// - 拒绝空路径
/// - 拒绝绝对路径
/// - 拼接后规范化，检查前缀是否仍在 root 内
fn try_resolve_path_under_root(root: &Path, relative: &str) -> Option<PathBuf> {
    let trimmed = relative.trim();
    if trimmed.is_empty() {
        return None;
    }
    let relative_path = Path::new(trimmed);
    // 拒绝绝对路径
    if relative_path.is_absolute() {
        return None;
    }
    // 拒绝以 / 或 \ 开头
    if trimmed.starts_with('/') || trimmed.starts_with('\\') {
        return None;
    }
    // 拒绝包含盘符的路径（如 C:\...）
    if trimmed.len() >= 2 && trimmed.as_bytes()[1] == b':' {
        return None;
    }
    let mut safe_relative = PathBuf::new();
    for component in relative_path.components() {
        match component {
            Component::Normal(part) => safe_relative.push(part),
            Component::CurDir => {}
            Component::ParentDir | Component::RootDir | Component::Prefix(_) => return None,
        }
    }
    if safe_relative.as_os_str().is_empty() {
        return None;
    }

    let root_canonical = match fs::canonicalize(root) {
        Ok(p) => p,
        Err(_) => root.to_path_buf(),
    };
    if has_link_like_component(&root_canonical, &safe_relative) {
        return None;
    }
    let combined = root.join(&safe_relative);
    // 已存在路径直接规范化；缺失的复制目标从规范化后的根目录拼接，避免 Windows 大小写差异。
    let canonical = match fs::canonicalize(&combined) {
        Ok(p) => p,
        Err(_) => root_canonical.join(&safe_relative),
    };

    if canonical.starts_with(&root_canonical) {
        Some(canonical)
    } else {
        None
    }
}

/// 判断路径本身是否为符号链接或 Windows 重解析点。
fn is_link_like_path(path: &Path) -> bool {
    let Ok(metadata) = fs::symlink_metadata(path) else {
        return false;
    };
    if metadata.file_type().is_symlink() {
        return true;
    }
    #[cfg(windows)]
    {
        metadata.file_attributes() & FILE_ATTRIBUTE_REPARSE_POINT != 0
    }
    #[cfg(not(windows))]
    {
        false
    }
}

/// 检查 root/relative 中所有已存在的路径组件是否包含链接类对象。
fn has_link_like_component(root: &Path, relative: &Path) -> bool {
    let mut current = root.to_path_buf();
    if is_link_like_path(&current) {
        return true;
    }
    for component in relative.components() {
        let Component::Normal(part) = component else {
            return true;
        };
        current.push(part);
        if is_link_like_path(&current) {
            return true;
        }
    }
    false
}

// ---------------------------------------------------------------------------
// 等待父进程退出
// ---------------------------------------------------------------------------

/// 等待主程序进程退出，避免 Windows 文件锁阻止覆盖。
#[cfg(windows)]
fn wait_for_parent_process(parent_pid: u32) {
    unsafe {
        let handle = OpenProcess(PROCESS_SYNCHRONIZE, 0, parent_pid);
        if handle == INVALID_HANDLE_VALUE || handle.is_null() {
            // 进程已退出或无法打开，直接继续
            return;
        }
        loop {
            let result = WaitForSingleObject(handle, PARENT_WAIT_TIMEOUT_MS);
            // WAIT_OBJECT_0 (等待对象已触发) → 进程已退出
            if result == 0 {
                break;
            }
            // WAIT_TIMEOUT (258) → 等待超时、继续轮询等待
            // 其他错误 → 退出循环
            if result != 258 {
                break;
            }
        }
        CloseHandle(handle);
    }
}

/// 非 Windows 平台没有 Windows 文件锁等待需求。
#[cfg(not(windows))]
fn wait_for_parent_process(_parent_pid: u32) {}

// ---------------------------------------------------------------------------
// 文件操作
// ---------------------------------------------------------------------------

#[cfg(windows)]
#[allow(clippy::permissions_set_readonly_false)]
/// 递归清除只读属性，便于删除 Windows 上的只读文件。
fn clear_readonly_recursive(path: &Path) {
    if is_link_like_path(path) {
        return;
    }
    if path.is_dir()
        && let Ok(entries) = fs::read_dir(path)
    {
        for entry in entries.flatten() {
            clear_readonly_recursive(&entry.path());
        }
    }

    if let Ok(metadata) = fs::metadata(path) {
        let mut permissions = metadata.permissions();
        if permissions.readonly() {
            // 在 Windows 上，只读文件(read-only files)可能导致递归删除返回“拒绝访问(access denied)”
            permissions.set_readonly(false);
            let _ = fs::set_permissions(path, permissions);
        }
    }
}

#[cfg(not(windows))]
/// 非 Windows 平台无需清除只读属性。
fn clear_readonly_recursive(_path: &Path) {}

/// 递归删除目录（忽略错误）
fn remove_dir_all_safe(path: &Path, logger: &mut Logger) -> bool {
    if !path.exists() {
        return true;
    }

    if is_link_like_path(path) {
        let removed = fs::remove_file(path).or_else(|_| fs::remove_dir(path));
        return match removed {
            Ok(_) => {
                logger.log(&format!("已删除链接/重解析点: {}", path.display()));
                true
            }
            Err(e) => {
                logger.log(&format!("删除链接/重解析点失败: {} ({e})", path.display()));
                false
            }
        };
    }

    clear_readonly_recursive(path);
    match fs::remove_dir_all(path) {
        Ok(_) => {
            logger.log(&format!("已删除目录: {}", path.display()));
            true
        }
        Err(e) => {
            logger.log(&format!("删除目录失败: {} ({e})", path.display()));
            false
        }
    }
}

/// 删除文件（忽略错误）
fn remove_file_safe(path: &Path) {
    if path.is_file() {
        let _ = fs::remove_file(path);
    }
}

/// 尝试删除空目录（仅空目录成功）
fn try_remove_empty_dir(path: &Path) {
    if path.is_dir() {
        let _ = fs::remove_dir(path);
    }
}

#[cfg(windows)]
/// 在 Windows 上启动后台命令，等待 updater 退出后重试删除目录。
fn schedule_remove_dir_after_exit(path: &Path, logger: &mut Logger) {
    let dir = path.to_string_lossy();
    let script = format!(
        "for /l %i in (1,1,20) do (rmdir /s /q \"{dir}\" 2>NUL && exit /b 0 & ping 127.0.0.1 -n 2 >NUL)"
    );
    match Command::new("cmd")
        .args(["/C", &script])
        .creation_flags(CREATE_NO_WINDOW_FLAG)
        .spawn()
    {
        Ok(_) => logger.log(&format!("已安排延迟清理目录: {}", path.display())),
        Err(e) => logger.log(&format!("安排延迟清理目录失败: {} ({e})", path.display())),
    }
}

#[cfg(not(windows))]
/// 非 Windows 平台暂不支持退出后延迟删除目录。
fn schedule_remove_dir_after_exit(path: &Path, logger: &mut Logger) {
    logger.log(&format!("当前平台不支持延迟清理目录: {}", path.display()));
}

#[cfg(windows)]
/// 更新器退出后在隐藏后台进程中重试删除文件。
fn schedule_remove_file_after_exit(path: &Path, logger: &mut Logger) {
    let file = path.to_string_lossy();
    let script = format!(
        "for /l %i in (1,1,20) do (del /f /q \"{file}\" 2>NUL && exit /b 0 & ping 127.0.0.1 -n 2 >NUL)"
    );
    match Command::new("cmd")
        .args(["/C", &script])
        .creation_flags(CREATE_NO_WINDOW_FLAG)
        .spawn()
    {
        Ok(_) => logger.log(&format!("已安排延迟清理文件: {}", path.display())),
        Err(e) => logger.log(&format!("安排延迟清理文件失败: {} ({e})", path.display())),
    }
}

#[cfg(not(windows))]
/// 非 Windows 平台暂不实现延迟文件删除。
fn schedule_remove_file_after_exit(path: &Path, logger: &mut Logger) {
    logger.log(&format!("当前平台不支持延迟清理文件: {}", path.display()));
}

/// 在安装目录同盘生成本次更新的备份目录。
fn build_backup_dir(root_dir: &Path) -> PathBuf {
    let pid = std::process::id();
    for index in 0..=999 {
        let name = if index == 0 {
            format!("{BACKUP_DIR_PREFIX}{pid}")
        } else {
            format!("{BACKUP_DIR_PREFIX}{pid}_{index}")
        };
        let path = root_dir.join(name);
        if !path.exists() {
            return path;
        }
    }
    root_dir.join(format!("{BACKUP_DIR_PREFIX}{pid}_fallback"))
}

/// 判断路径是否为 updater 遗留的备份目录。
fn is_update_backup_dir(path: &Path) -> bool {
    path.is_dir()
        && !is_link_like_path(path)
        && path
            .file_name()
            .and_then(|name| name.to_str())
            .map(|name| name.starts_with(BACKUP_DIR_PREFIX))
            .unwrap_or(false)
}

/// 优先直接删除目录；失败时安排后台延迟清理。
fn remove_dir_all_or_schedule(path: &Path, logger: &mut Logger) {
    if !remove_dir_all_safe(path, logger) && path.exists() {
        logger.log("目录直接清理未完成，安排延迟重试");
        schedule_remove_dir_after_exit(path, logger);
    }
}

/// 删除文件；如果立即删除失败，则安排更新器退出后重试。
fn remove_file_or_schedule(path: &Path, logger: &mut Logger) {
    if !path.exists() {
        return;
    }
    remove_file_safe(path);
    if path.exists() {
        logger.log("文件未能立即清理完成，安排延迟重试");
        schedule_remove_file_after_exit(path, logger);
    }
}

/// 清理本次更新的解压目录、更新包和计划文件。
fn cleanup_update_artifacts(
    extract_dir: &Path,
    package_path: &Path,
    plan_file: &Path,
    logger: &mut Logger,
) {
    logger.log("清理本次更新临时文件...");
    remove_file_or_schedule(plan_file, logger);

    let running_from_extract = env::current_exe()
        .map(|p| p.starts_with(extract_dir))
        .unwrap_or(false);
    if running_from_extract {
        logger.log("更新器正在解压目录中运行，安排退出后延迟清理临时目录");
        schedule_remove_dir_after_exit(extract_dir, logger);
    } else {
        remove_dir_all_or_schedule(extract_dir, logger);
    }

    remove_file_or_schedule(package_path, logger);
    if let Some(package_dir) = package_path.parent() {
        try_remove_empty_dir(package_dir);
    }
}

/// 清理上次更新可能遗留的备份目录。
fn cleanup_stale_backup_dirs(root_dir: &Path, logger: &mut Logger) {
    let Ok(entries) = fs::read_dir(root_dir) else {
        return;
    };

    for entry in entries.flatten() {
        let path = entry.path();
        if !is_update_backup_dir(&path) {
            continue;
        }
        logger.log(&format!("清理上次遗留的备份目录: {}", path.display()));
        remove_dir_all_or_schedule(&path, logger);
    }
}

/// 递归清理空目录
fn clean_empty_dirs_recursive(dir: &Path) {
    if !dir.is_dir() {
        return;
    }
    // 先递归处理子目录
    if let Ok(entries) = fs::read_dir(dir) {
        for entry in entries.flatten() {
            if entry.file_type().map(|t| t.is_dir()).unwrap_or(false) {
                clean_empty_dirs_recursive(&entry.path());
            }
        }
    }
    // 然后尝试删除自身（如果为空）
    let _ = fs::remove_dir(dir);
}

/// 将 `_backup` 中的文件恢复到安装目录，用于复制阶段失败后的尽力回滚。
///
/// 回滚不能保证覆盖所有外部错误（例如权限或磁盘故障），但必须避免把
/// 已经备份的旧文件遗留在临时目录中而导致安装目录不可运行。
fn restore_backup_recursive(root: &Path, backup_root: &Path, logger: &mut Logger) -> u32 {
    /// 递归恢复单个备份目录下的文件。
    fn restore_dir(root: &Path, backup_root: &Path, current: &Path, logger: &mut Logger) -> u32 {
        let mut restored = 0;
        let entries = match fs::read_dir(current) {
            Ok(entries) => entries,
            Err(e) => {
                logger.log(&format!("  读取备份目录失败: {} ({e})", current.display()));
                return 0;
            }
        };

        for entry in entries.flatten() {
            let backup_path = entry.path();
            if backup_path.is_dir() {
                restored += restore_dir(root, backup_root, &backup_path, logger);
                let _ = fs::remove_dir(&backup_path);
                continue;
            }
            if !backup_path.is_file() {
                continue;
            }
            let rel = match backup_path.strip_prefix(backup_root) {
                Ok(p) => p,
                Err(_) => continue,
            };
            let rel_text = rel.to_string_lossy();
            let Some(target) = try_resolve_path_under_root(root, &rel_text) else {
                logger.log(&format!("  跳过不安全的备份路径: {rel_text}"));
                continue;
            };
            if let Some(parent) = target.parent() {
                let _ = fs::create_dir_all(parent);
            }
            if target.is_dir() {
                let _ = fs::remove_dir_all(&target);
            } else if target.exists() {
                let _ = fs::remove_file(&target);
            }
            match fs::rename(&backup_path, &target) {
                Ok(_) => restored += 1,
                Err(e) => logger.log(&format!("  恢复备份失败: {rel_text} ({e})")),
            }
        }

        restored
    }

    if !backup_root.is_dir() {
        return 0;
    }
    restore_dir(root, backup_root, backup_root, logger)
}

/// 移动文件/目录到备份目录。如果目标已存在，添加 .bak 后缀。
fn move_to_backup(source: &Path, backup: &Path) -> std::io::Result<()> {
    if !source.exists() {
        return Ok(());
    }
    if let Some(parent) = backup.parent() {
        fs::create_dir_all(parent)?;
    }
    // 如果备份目标已存在，添加后缀
    let mut final_backup = backup.to_path_buf();
    if final_backup.exists() {
        for i in 1..=999 {
            let with_ext = backup.with_extension(format!("bak{i:03}"));
            if !with_ext.exists() {
                final_backup = with_ext;
                break;
            }
        }
    }
    fs::rename(source, &final_backup)
}

/// 为目标文件生成位于同一目录下的临时复制文件路径。
fn temp_copy_path_for_target(target: &Path, index: u32) -> io::Result<PathBuf> {
    let file_name = target
        .file_name()
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "目标路径缺少文件名"))?
        .to_string_lossy();
    let temp_name = format!(".{file_name}.update-tmp-{}-{index}", std::process::id());
    Ok(target.with_file_name(temp_name))
}

/// 先把源文件完整复制到目标目录旁的唯一临时文件，成功后返回临时文件路径。
fn copy_file_to_unique_temp(source: &Path, target: &Path) -> io::Result<PathBuf> {
    let mut last_exists = false;
    for index in 0..=999 {
        let temp_path = temp_copy_path_for_target(target, index)?;
        let mut output = match fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&temp_path)
        {
            Ok(file) => file,
            Err(e) if e.kind() == io::ErrorKind::AlreadyExists => {
                last_exists = true;
                continue;
            }
            Err(e) => return Err(e),
        };

        let copy_result = (|| -> io::Result<()> {
            let mut input = fs::File::open(source)?;
            io::copy(&mut input, &mut output)?;
            output.sync_all()?;
            Ok(())
        })();

        if let Err(e) = copy_result {
            let _ = fs::remove_file(&temp_path);
            return Err(e);
        }
        return Ok(temp_path);
    }

    let reason = if last_exists {
        "所有临时复制文件名均已存在"
    } else {
        "无法分配临时复制文件路径"
    };
    Err(io::Error::new(io::ErrorKind::AlreadyExists, reason))
}

fn compute_sha256_hex(path: &Path) -> io::Result<String> {
    let mut file = fs::File::open(path)?;
    let mut hasher = Sha256::new();
    let mut buffer = vec![0u8; 8192];
    loop {
        let read = file.read(&mut buffer)?;
        if read == 0 {
            break;
        }
        hasher.update(&buffer[..read]);
    }
    Ok(format!("{:x}", hasher.finalize()))
}

fn expected_copy_hash<'a>(copy_hashes: &'a HashMap<String, String>, rel: &str) -> Option<&'a str> {
    copy_hashes
        .get(rel)
        .or_else(|| copy_hashes.get(&rel.replace('\\', "/")))
        .map(String::as_str)
}

fn sha256_matches(actual: &str, expected: &str) -> bool {
    actual.eq_ignore_ascii_case(expected.trim())
}

// ---------------------------------------------------------------------------
// 主逻辑
// ---------------------------------------------------------------------------

/// 按命令行协议执行一次更新流程，并返回进程退出码。
fn run_with_args(args: Vec<String>) -> i32 {
    // 命令行参数是 updater 和 Python installer 之间的兼容协议。
    // 如需扩展，只能新增可选参数或 plan 字段，避免旧主程序无法调用新版 updater。
    // 检查 --show-console flag（预留，未来用于控制台窗口显示）
    let _show_console = args.iter().any(|a| a == "--show-console");

    // 过滤掉 flag，只保留位置参数
    let positional: Vec<&String> = args.iter().filter(|a| *a != "--show-console").collect();

    if positional.len() < 9 {
        eprintln!("用法: eer_updater.exe <ParentPid> <RootDir> <ExtractDir> <PackagePath>");
        eprintln!("       <SuccessStatusFile> <FailureStatusFile> <RelaunchExecutable> <PlanFile>");
        eprintln!("       [--show-console]");
        return 2;
    }

    let parent_pid: u32 = match positional[1].parse() {
        Ok(v) => v,
        Err(_) => {
            eprintln!("错误: ParentPid 必须是有效的数字");
            return 2;
        }
    };
    let root_dir = PathBuf::from(&positional[2]);
    let extract_dir = PathBuf::from(&positional[3]);
    let package_path = PathBuf::from(&positional[4]);
    let success_file = PathBuf::from(&positional[5]);
    let failure_file = PathBuf::from(&positional[6]);
    let relaunch_exe = PathBuf::from(&positional[7]);
    let plan_file = PathBuf::from(&positional[8]);

    // 初始化日志
    let log_path = root_dir.join("logs").join("updater.log");
    let mut logger = Logger::init(&log_path);
    logger.log("=== EER Updater 启动 ===");
    logger.log(&format!("RootDir: {}", root_dir.display()));
    logger.log(&format!("ExtractDir: {}", extract_dir.display()));
    logger.log(&format!("PlanFile: {}", plan_file.display()));

    // 阶段 1：等待父进程退出
    logger.log(&format!("等待父进程退出 (PID: {parent_pid})..."));
    wait_for_parent_process(parent_pid);
    logger.log("父进程已退出");

    // 阶段 2：安全检查
    if is_drive_root_directory(&root_dir) {
        let reason = "检测到安装在盘符根目录，已阻止更新。请将程序移动到子文件夹后再试。\n\
                      Detected installation in drive root. Update blocked.";
        logger.log(&format!("安全检查失败: {reason}"));
        write_status_file(&failure_file, reason);
        cleanup_update_artifacts(&extract_dir, &package_path, &plan_file, &mut logger);
        return 2;
    }

    // 阶段 3：读取 plan JSON
    let plan_content = match fs::read_to_string(&plan_file) {
        Ok(c) => c,
        Err(e) => {
            let reason = format!("无法读取 plan 文件: {e}");
            logger.log(&reason);
            write_status_file(&failure_file, &reason);
            cleanup_update_artifacts(&extract_dir, &package_path, &plan_file, &mut logger);
            return 2;
        }
    };
    let plan: UpdatePlan = match serde_json::from_str(&plan_content) {
        Ok(p) => p,
        Err(e) => {
            let reason = format!("plan JSON 解析失败: {e}");
            logger.log(&reason);
            write_status_file(&failure_file, &reason);
            cleanup_update_artifacts(&extract_dir, &package_path, &plan_file, &mut logger);
            return 2;
        }
    };
    logger.log(&format!(
        "plan 加载完成: package_type={}, remove={}, copy={}, copy_hashes={}, protected={}",
        plan.package_type,
        plan.remove_list.len(),
        plan.copy_list.len(),
        plan.copy_hashes.len(),
        plan.protected_list.len()
    ));
    if plan.copy_hashes.is_empty() {
        logger.log("plan 未提供 copy_hashes，将按旧版兼容模式跳过复制前 SHA-256 校验");
    }

    // 阶段 4：执行更新
    cleanup_stale_backup_dirs(&root_dir, &mut logger);

    // 备份目录必须与安装目录同盘，因为 Windows 不能跨盘 rename。
    // 解压目录可能位于系统临时目录，和安装目录不一定在同一个盘。
    let backup_dir = build_backup_dir(&root_dir);
    let _ = fs::create_dir_all(&backup_dir);
    logger.log(&format!("备份目录: {}", backup_dir.display()));

    let protected_normalized: Vec<String> = plan
        .protected_list
        .iter()
        .map(|s| s.replace('/', "\\"))
        .collect();
    let protected_set: HashSet<&str> = protected_normalized.iter().map(|s| s.as_str()).collect();
    let mut success = true;
    let mut failure_reason = String::new();
    // 记录本次新增的文件；如果后续复制失败，先删除这些新文件再恢复旧备份。
    let mut copied_new_targets: Vec<PathBuf> = Vec::new();

    // 4a：删除旧文件（移动到备份目录）
    logger.log("开始删除旧文件...");
    let mut delete_count = 0u32;
    for rel in &plan.remove_list {
        let rel_normalized = rel.replace('/', "\\");
        // 跳过 protected 文件
        if is_protected(&rel_normalized, &protected_set) {
            continue;
        }
        if let Some(target) = try_resolve_path_under_root(&root_dir, &rel_normalized)
            && target.exists()
        {
            let backup_target = backup_dir.join(&rel_normalized);
            if let Err(e) = move_to_backup(&target, &backup_target) {
                logger.log(&format!("  备份失败: {rel_normalized} ({e})，尝试直接删除"));
                if target.is_dir() {
                    remove_dir_all_safe(&target, &mut logger);
                } else {
                    remove_file_safe(&target);
                }
            }
            delete_count += 1;
        }
    }
    logger.log(&format!("已删除 {delete_count} 个旧文件"));

    // 4b：清理空目录
    logger.log("清理空目录...");
    // 第一轮：删除已删除文件的父目录（如果是空的）
    for rel in &plan.remove_list {
        let rel_normalized = rel.replace('/', "\\");
        if let Some(target) = try_resolve_path_under_root(&root_dir, &rel_normalized)
            && let Some(parent) = target.parent()
        {
            try_remove_empty_dir(parent);
        }
    }
    // 第二轮：递归清理 _internal 下的空目录
    let internal_dir = root_dir.join("_internal");
    if internal_dir.is_dir()
        && let Ok(entries) = fs::read_dir(&internal_dir)
    {
        for entry in entries.flatten() {
            if entry.file_type().map(|t| t.is_dir()).unwrap_or(false) {
                clean_empty_dirs_recursive(&entry.path());
            }
        }
    }
    logger.log("空目录清理完成");

    // 4c：复制新文件
    logger.log("开始复制新文件...");
    let mut copy_count = 0u32;
    for rel in &plan.copy_list {
        let rel_normalized = rel.replace('/', "\\");
        // 跳过 protected 文件
        if is_protected(&rel_normalized, &protected_set) {
            continue;
        }
        let target = match try_resolve_path_under_root(&root_dir, &rel_normalized) {
            Some(p) => p,
            None => {
                logger.log(&format!("  跳过（路径穿越）: {rel_normalized}"));
                success = false;
                if failure_reason.is_empty() {
                    failure_reason = format!("copy path escapes install root: {rel_normalized}");
                }
                continue;
            }
        };
        let source = match try_resolve_path_under_root(&extract_dir, &rel_normalized) {
            Some(p) => p,
            None => {
                logger.log(&format!("  copy source path is unsafe: {rel_normalized}"));
                success = false;
                if failure_reason.is_empty() {
                    failure_reason = format!("copy source path is unsafe: {rel_normalized}");
                }
                continue;
            }
        };
        if !source.is_file() {
            logger.log(&format!("  copy source file is missing: {rel_normalized}"));
            success = false;
            if failure_reason.is_empty() {
                failure_reason = format!("update package is missing file: {rel_normalized}");
            }
            continue;
        }
        if let Some(expected_hash) = expected_copy_hash(&plan.copy_hashes, rel) {
            match compute_sha256_hex(&source) {
                Ok(actual_hash) if sha256_matches(&actual_hash, expected_hash) => {}
                Ok(actual_hash) => {
                    logger.log(&format!(
                        "  SHA-256 校验失败: {rel_normalized} (expected={expected_hash}, actual={actual_hash})"
                    ));
                    success = false;
                    if failure_reason.is_empty() {
                        failure_reason = format!("SHA-256 校验失败: {rel_normalized}");
                    }
                    continue;
                }
                Err(e) => {
                    logger.log(&format!("  SHA-256 计算失败: {rel_normalized} ({e})"));
                    success = false;
                    if failure_reason.is_empty() {
                        failure_reason = format!("SHA-256 计算失败: {rel_normalized} ({e})");
                    }
                    continue;
                }
            }
        } else if !plan.copy_hashes.is_empty() {
            logger.log(&format!(
                "  未找到 SHA-256，按兼容模式跳过校验: {rel_normalized}"
            ));
        }
        // 确保目标父目录存在
        if let Some(parent) = target.parent() {
            let _ = fs::create_dir_all(parent);
        }
        let target_existed = target.exists();
        let temp_target = match copy_file_to_unique_temp(&source, &target) {
            Ok(path) => path,
            Err(e) => {
                logger.log(&format!("  复制到临时文件失败: {rel_normalized} ({e})"));
                success = false;
                if failure_reason.is_empty() {
                    failure_reason = format!("复制文件失败: {rel_normalized} ({e})");
                }
                continue;
            }
        };
        // 先完整写入新文件，再移动旧目标到备份目录，避免目标文件半写。
        if target.exists() {
            let backup_target = backup_dir.join(&rel_normalized);
            if let Err(e) = move_to_backup(&target, &backup_target) {
                logger.log(&format!("  备份失败: {rel_normalized} ({e})"));
                remove_file_safe(&temp_target);
                success = false;
                if failure_reason.is_empty() {
                    failure_reason = format!("备份文件失败: {rel_normalized} ({e})");
                }
                continue;
            }
        }
        if let Err(e) = fs::rename(&temp_target, &target) {
            logger.log(&format!("  原子替换失败: {rel_normalized} ({e})"));
            remove_file_safe(&temp_target);
            success = false;
            if failure_reason.is_empty() {
                failure_reason = format!("替换文件失败: {rel_normalized} ({e})");
            }
        } else {
            if !target_existed {
                copied_new_targets.push(target);
            }
            copy_count += 1;
        }
    }
    logger.log(&format!("已复制 {copy_count} 个新文件"));

    if !success {
        logger.log(&format!("更新失败: {failure_reason}"));
        for target in &copied_new_targets {
            remove_file_safe(target);
        }
        logger.log("开始回滚已备份文件...");
        let restored = restore_backup_recursive(&root_dir, &backup_dir, &mut logger);
        logger.log(&format!("已回滚 {restored} 个文件"));
        cleanup_update_artifacts(&extract_dir, &package_path, &plan_file, &mut logger);
        remove_dir_all_or_schedule(&backup_dir, &mut logger);
        write_status_file(&failure_file, &failure_reason);
        return 2;
    }

    // 4d：恢复 protected 文件
    logger.log("恢复 protected 文件...");
    for rel in &plan.protected_list {
        let rel_normalized = rel.replace('/', "\\");
        // 跳过目录条目（如 logs/）
        if rel_normalized.ends_with('\\') || rel_normalized.ends_with('/') {
            continue;
        }
        let backup_file = backup_dir.join(&rel_normalized);
        if backup_file.exists() {
            let target = root_dir.join(&rel_normalized);
            if let Some(parent) = target.parent() {
                let _ = fs::create_dir_all(parent);
            }
            if let Err(e) = fs::copy(&backup_file, &target) {
                logger.log(&format!("  恢复失败: {rel_normalized} ({e})"));
            } else {
                logger.log(&format!("  已恢复: {rel_normalized}"));
            }
        }
    }

    // 阶段 5：清理
    logger.log("清理临时文件...");
    let running_from_extract = env::current_exe()
        .map(|p| p.starts_with(&extract_dir))
        .unwrap_or(false);
    if running_from_extract {
        logger.log("更新器正在临时目录中运行，退出后延迟清理临时目录");
        schedule_remove_dir_after_exit(&extract_dir, &mut logger);
    } else {
        remove_dir_all_safe(&extract_dir, &mut logger);
        if extract_dir.exists() {
            logger.log("临时目录直接清理未完成，安排延迟重试");
            schedule_remove_dir_after_exit(&extract_dir, &mut logger);
        }
    }
    remove_file_safe(&plan_file);
    remove_file_safe(&package_path);
    if let Some(package_dir) = package_path.parent() {
        try_remove_empty_dir(package_dir);
    }
    remove_dir_all_or_schedule(&backup_dir, &mut logger);

    // 阶段 6：写入成功状态
    write_status_file(&success_file, "succeeded");
    remove_file_safe(&failure_file);
    logger.log("更新成功！");

    // 阶段 7：重启主程序
    if relaunch_exe.exists() {
        logger.log(&format!("重启主程序: {}", relaunch_exe.display()));
        let work_dir = relaunch_exe.parent().unwrap_or(&root_dir);
        match Command::new(&relaunch_exe).current_dir(work_dir).spawn() {
            Ok(_) => logger.log("主程序已启动"),
            Err(e) => logger.log(&format!("启动主程序失败: {e}（请手动启动）")),
        }
    } else {
        logger.log("未找到主程序，请手动启动");
    }

    0
}

/// 检查文件路径是否在 protected 集合中（精确匹配或前缀目录匹配）。
fn is_protected(file_path: &str, protected: &HashSet<&str>) -> bool {
    if protected.contains(file_path) {
        return true;
    }
    // 目录前缀匹配（如 logs/ 保护 logs/xxx）
    for p in protected {
        if (p.ends_with('/') || p.ends_with('\\')) && file_path.starts_with(p) {
            return true;
        }
    }
    false
}

/// 写入成功或失败状态文件，供 Python/前端侧诊断更新结果。
fn write_status_file(path: &Path, content: &str) {
    if let Some(parent) = path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    let _ = fs::write(path, content);
}

/// 程序入口：执行更新流程并使用流程结果作为退出码。
fn main() {
    let code = run_with_args(env::args().collect());
    std::process::exit(code);
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    /// 创建带进程号和时间戳的测试临时目录。
    fn test_dir(name: &str) -> PathBuf {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let dir = env::current_dir()
            .unwrap()
            .join("target")
            .join("updater-tests")
            .join(format!("{name}-{}-{unique}", std::process::id()));
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    /// 路径解析应拒绝所有父目录穿越片段。
    fn resolve_rejects_parent_dir_segments() {
        let root = Path::new(r"C:\app");

        assert!(try_resolve_path_under_root(root, r"..\evil.txt").is_none());
        assert!(try_resolve_path_under_root(root, r"safe\..\evil.txt").is_none());
        assert!(try_resolve_path_under_root(root, "../evil.txt").is_none());
        assert!(try_resolve_path_under_root(root, ".").is_none());
    }

    #[test]
    /// 路径解析应接受普通相对路径。
    fn resolve_accepts_normal_relative_path() {
        let root = Path::new(r"C:\app");
        let resolved = try_resolve_path_under_root(root, r"_internal\app.dll").unwrap();

        assert!(resolved.starts_with(root));
    }

    #[test]
    #[cfg(windows)]
    /// 在 Windows 下根目录大小写不一致时，缺失目标仍应解析到规范根目录内。
    fn resolve_accepts_missing_file_when_root_casing_differs() {
        let base = test_dir("case-root");
        let root = base.join("MixedCaseRoot");
        fs::create_dir_all(&root).unwrap();
        let canonical_root = fs::canonicalize(&root).unwrap();
        let lower_root = PathBuf::from(canonical_root.to_string_lossy().to_lowercase());

        let resolved = try_resolve_path_under_root(&lower_root, "README.md").unwrap();

        assert!(resolved.starts_with(&canonical_root));
        assert!(resolved.ends_with("README.md"));

        let _ = fs::remove_dir_all(base);
    }

    #[test]
    /// 缺少复制源文件时，更新应失败并移除本次已新增文件。
    fn missing_copy_source_fails_and_removes_new_files() {
        let base = test_dir("missing-source");
        let root = base.join("root");
        let extract = base.join("extract");
        fs::create_dir_all(&root).unwrap();
        fs::create_dir_all(&extract).unwrap();
        fs::write(extract.join("present.dll"), "new").unwrap();

        let plan = r#"{
  "package_type": "manifest",
  "remove_list": [],
  "copy_list": ["present.dll", "missing.dll"],
  "protected_list": []
}"#;
        let plan_path = extract.join("_plan.json");
        fs::write(&plan_path, plan).unwrap();
        let success_file = root.join("_update_success.txt");
        let failure_file = root.join("_update_failure.txt");

        let code = run_with_args(vec![
            "eer_updater.exe".to_string(),
            "0".to_string(),
            root.to_string_lossy().into_owned(),
            extract.to_string_lossy().into_owned(),
            root.join("_updates")
                .join("package.zip")
                .to_string_lossy()
                .into_owned(),
            success_file.to_string_lossy().into_owned(),
            failure_file.to_string_lossy().into_owned(),
            root.join("missing-main.exe").to_string_lossy().into_owned(),
            plan_path.to_string_lossy().into_owned(),
        ]);

        assert_eq!(code, 2);
        assert!(!success_file.exists());
        assert!(failure_file.exists());
        assert!(!root.join("present.dll").exists());

        let _ = fs::remove_dir_all(base);
    }

    #[test]
    /// 复制阶段失败时，应从备份恢复已存在的旧文件。
    fn copy_failure_rolls_back_existing_file() {
        let base = test_dir("rollback-existing");
        let root = base.join("root");
        let extract = base.join("extract");
        fs::create_dir_all(&root).unwrap();
        fs::create_dir_all(&extract).unwrap();
        fs::write(root.join("app.dll"), "old").unwrap();
        fs::write(extract.join("app.dll"), "new").unwrap();

        let plan = r#"{
  "package_type": "manifest",
  "remove_list": [],
  "copy_list": ["app.dll", "missing.dll"],
  "protected_list": []
}"#;
        let plan_path = extract.join("_plan.json");
        fs::write(&plan_path, plan).unwrap();
        let success_file = root.join("_update_success.txt");
        let failure_file = root.join("_update_failure.txt");

        let code = run_with_args(vec![
            "eer_updater.exe".to_string(),
            "0".to_string(),
            root.to_string_lossy().into_owned(),
            extract.to_string_lossy().into_owned(),
            root.join("_updates")
                .join("package.zip")
                .to_string_lossy()
                .into_owned(),
            success_file.to_string_lossy().into_owned(),
            failure_file.to_string_lossy().into_owned(),
            root.join("missing-main.exe").to_string_lossy().into_owned(),
            plan_path.to_string_lossy().into_owned(),
        ]);

        assert_eq!(code, 2);
        assert_eq!(fs::read_to_string(root.join("app.dll")).unwrap(), "old");

        let _ = fs::remove_dir_all(base);
    }

    #[test]
    /// copy_hashes 不匹配时，应拒绝复制并保留旧文件。
    fn copy_hash_mismatch_fails_before_replacing_target() {
        let base = test_dir("hash-mismatch");
        let root = base.join("root");
        let extract = base.join("extract");
        fs::create_dir_all(&root).unwrap();
        fs::create_dir_all(&extract).unwrap();
        fs::write(root.join("app.dll"), "old").unwrap();
        fs::write(extract.join("app.dll"), "new").unwrap();

        let plan = r#"{
  "package_type": "manifest",
  "remove_list": [],
  "copy_list": ["app.dll"],
  "copy_hashes": {"app.dll": "0000000000000000000000000000000000000000000000000000000000000000"},
  "protected_list": []
}"#;
        let plan_path = extract.join("_plan.json");
        fs::write(&plan_path, plan).unwrap();
        let success_file = root.join("_update_success.txt");
        let failure_file = root.join("_update_failure.txt");

        let code = run_with_args(vec![
            "eer_updater.exe".to_string(),
            "0".to_string(),
            root.to_string_lossy().into_owned(),
            extract.to_string_lossy().into_owned(),
            root.join("_updates")
                .join("package.zip")
                .to_string_lossy()
                .into_owned(),
            success_file.to_string_lossy().into_owned(),
            failure_file.to_string_lossy().into_owned(),
            root.join("missing-main.exe").to_string_lossy().into_owned(),
            plan_path.to_string_lossy().into_owned(),
        ]);

        assert_eq!(code, 2);
        assert_eq!(fs::read_to_string(root.join("app.dll")).unwrap(), "old");
        assert!(failure_file.exists());

        let _ = fs::remove_dir_all(base);
    }

    #[test]
    /// SHA-256 helper 应返回标准小写十六进制摘要。
    fn computes_sha256_hex() {
        let base = test_dir("sha256");
        let file = base.join("payload.bin");
        fs::write(&file, "abc").unwrap();

        assert_eq!(
            compute_sha256_hex(&file).unwrap(),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        );

        let _ = fs::remove_dir_all(base);
    }

    #[test]
    /// 临时复制文件应位于目标目录，rename 后不应残留。
    fn copy_to_temp_uses_target_directory_and_cleans_on_rename() {
        // 验证临时文件与目标文件同目录，便于后续 rename 保持原子性。
        let base = test_dir("atomic-copy");
        let source = base.join("source.dll");
        let target = base.join("nested").join("app.dll");
        fs::create_dir_all(target.parent().unwrap()).unwrap();
        fs::write(&source, "new").unwrap();

        let temp = copy_file_to_unique_temp(&source, &target).unwrap();
        assert_eq!(temp.parent(), target.parent());
        assert!(
            temp.file_name()
                .unwrap()
                .to_string_lossy()
                .contains("update-tmp")
        );
        fs::rename(&temp, &target).unwrap();

        assert_eq!(fs::read_to_string(&target).unwrap(), "new");
        assert!(!temp.exists());

        let _ = fs::remove_dir_all(base);
    }

    #[test]
    /// 如环境允许创建符号链接，链接目录下的缺失目标应被拒绝。
    fn resolve_rejects_missing_target_under_symlink_dir_when_possible() {
        // 验证符号链接目录下的缺失目标不会被解析为可写入路径。
        let base = test_dir("symlink-dir");
        let root = base.join("root");
        let outside = base.join("outside");
        fs::create_dir_all(&root).unwrap();
        fs::create_dir_all(&outside).unwrap();
        let link = root.join("linked");

        #[cfg(windows)]
        {
            if std::os::windows::fs::symlink_dir(&outside, &link).is_err() {
                let _ = fs::remove_dir_all(base);
                return;
            }
        }
        #[cfg(unix)]
        {
            if std::os::unix::fs::symlink(&outside, &link).is_err() {
                let _ = fs::remove_dir_all(base);
                return;
            }
        }

        assert!(try_resolve_path_under_root(&root, r"linked\new.dll").is_none());

        let _ = fs::remove_dir_all(base);
    }

    #[test]
    /// 清理遗留备份目录时，应能处理只读文件。
    fn stale_backup_cleanup_removes_backup_dirs() {
        let base = test_dir("stale-backup");
        let root = base.join("root");
        let backup = root.join(format!("{BACKUP_DIR_PREFIX}12345"));
        fs::create_dir_all(backup.join("_internal")).unwrap();
        let stale_file = backup.join("_internal").join("old.dll");
        fs::write(&stale_file, "old").unwrap();

        let mut permissions = fs::metadata(&stale_file).unwrap().permissions();
        permissions.set_readonly(true);
        fs::set_permissions(&stale_file, permissions).unwrap();

        let mut logger = Logger::init(&root.join("updater.log"));
        cleanup_stale_backup_dirs(&root, &mut logger);

        assert!(!backup.exists());

        let _ = fs::remove_dir_all(base);
    }
}
