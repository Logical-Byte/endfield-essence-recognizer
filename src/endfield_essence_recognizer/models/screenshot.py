from pydantic import BaseModel, Field


class ScreenshotRequest(BaseModel):
    should_focus: bool = Field(
        default=True,
        description="在截图前，是否自动将 Endfield 窗口置于前台",
    )
    post_process: bool = Field(
        default=True,
        description="是否对截图进行后处理，遮罩掉 UID 等敏感信息",
    )
    title: str = Field(
        default="Endfield",
        description="截图的标题，最终会作为文件名的一部分",
    )
    format: str = Field(
        default="png",
        description="截图的文件格式，支持 png、jpg",
    )


class ScreenshotResponse(BaseModel):
    success: bool
    message: str
    file_path: str | None = Field(
        default=None,
        description="保存的截图文件的完整路径",
    )
    file_name: str | None = Field(
        default=None,
        description="保存的截图文件名",
    )
