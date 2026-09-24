"""镜像源管理。"""

from __future__ import annotations

from endfield_essence_recognizer.updater.sources import (
    GITHUB_FLOW,
    MIRROR_CHYAN_FLOW,
    YITULIU_FLOW,
)

MIRRORS = {
    "github": "https://github.com/{repo}/releases/download/{tag}/{file}",
    # 主流稳定
    "ghproxy": "https://mirror.ghproxy.com/https://github.com/{repo}/releases/download/{tag}/{file}",
    "ghproxy_net": "https://ghproxy.net/https://github.com/{repo}/releases/download/{tag}/{file}",
    "ghproxy_homeboy": "https://ghproxy.homeboyc.cn/https://github.com/{repo}/releases/download/{tag}/{file}",
    # 其他常用代理镜像
    "gitmirror": "https://hub.gitmirror.com/https://github.com/{repo}/releases/download/{tag}/{file}",
    "gh_con": "https://gh.con.sh/https://github.com/{repo}/releases/download/{tag}/{file}",
    "githubproxy_cc": "https://githubproxy.cc/https://github.com/{repo}/releases/download/{tag}/{file}",
    "ghfast": "https://ghfast.top/https://github.com/{repo}/releases/download/{tag}/{file}",
    # Cloudflare Worker 类
    "gh_api": "https://gh.api.99988866.xyz/https://github.com/{repo}/releases/download/{tag}/{file}",
    # 兼容 fastgit 思路（部分地区可用）
    "fastgit": "https://download.fastgit.org/{repo}/releases/download/{tag}/{file}",
}

GITHUB_MIRROR_NAMES = {
    "github": "GitHub 官方",
    "ghproxy": "GHProxy 官方镜像",
    "ghproxy_net": "GHProxy 镜像（net）",
    "ghproxy_homeboy": "GHProxy 镜像（homeboy）",
    "gitmirror": "GitMirror 镜像",
    "gh_con": "gh.con.sh 镜像",
    "githubproxy_cc": "githubproxy.cc 镜像",
    "ghfast": "ghfast.top 镜像",
    "gh_api": "Cloudflare Worker 镜像",
    "fastgit": "FastGit 镜像（部分可用）",
}

MIRROR_NAMES = {
    YITULIU_FLOW: "一图流 API (CN 镜像)",
    MIRROR_CHYAN_FLOW: "Mirror 酱",
    GITHUB_FLOW: "GitHub Release",
    **GITHUB_MIRROR_NAMES,
}


def get_mirror_url(mirror: str, repo: str, tag: str, filename: str) -> str:
    """获取镜像源 URL"""
    template = MIRRORS.get(mirror, MIRRORS["github"])
    return template.format(repo=repo, tag=tag, file=filename)
