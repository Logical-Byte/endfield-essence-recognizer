from pydantic import BaseModel, Field

# image_base64 允许的最大字符数，防止超长请求体把服务进程内存推高，
# 并避免对超大字符串做一次同等规模的 base64 解码（内存 / CPU 放大）。
# 注意这层约束发生在 ASGI 读完整个请求体、并完成 JSON 解析之后，
# 拦不住任意大的 HTTP 负载本身，只保证超限的字符串不再进入 base64
# 解码与落盘：传输层限流尚未实现，当前只依赖 localhost 绑定。
# 路由对解码后的图片另有体积上限（api/routes/matrix_export.py 中的
# _MAX_EXPORT_BYTES = 32 * 1024 * 1024 原始字节，base64 编码后约
# 44,739,244 个字符、即约 42.7 MiB），这里取 48 MiB 字符留出余量：
# 既能拦住无限增长，又不会比路由更早拒绝路由本身允许的图片。
MAX_IMAGE_BASE64_CHARS: int = 48 * 1024 * 1024


class TreasureMatrixExportRequest(BaseModel):
    image_base64: str = Field(
        max_length=MAX_IMAGE_BASE64_CHARS,
        description="WebP 或 PNG 图片内容的 base64 编码（不含 data URI 前缀）",
    )
    open_folder: bool = Field(
        default=True,
        description="保存成功后是否打开图片所在的文件夹",
    )


class TreasureMatrixExportResponse(BaseModel):
    success: bool
    message: str
    file_path: str | None = Field(
        default=None,
        description="保存的导出图片的完整路径",
    )
    file_name: str | None = Field(
        default=None,
        description="保存的导出图片文件名",
    )
