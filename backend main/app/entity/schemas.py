"""
Pydantic 请求/响应模型
⽤于 API 接⼝的数据验证和序列化


分层原则：
  - Create 模型：创建资源时的请求体
  - Update 模型：更新资源时的请求体（所有字段可选）
  - Response 模型：API 返回的响应体（过滤敏感字段）
  - List 模型：分⻚列表查询的参数和响应
"""
from datetime import datetime
from typing import Literal, Optional


from pydantic import BaseModel, ConfigDict, Field


# ══════════════════════════════════════════════════════════════
# ⼀、⽤户与权限
# ══════════════════════════════════════════════════════════════


# --- 认证相关 ---


class UserRegister(BaseModel):
    """⽤户注册请求"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: str = Field(
        ...,
        pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
        description="邮箱",
        examples=["user@example.com"],
    )
    password: str = Field(..., min_length=6, max_length=100, description="密码")


class UserLogin(BaseModel):
    """⽤户登录请求"""
    username: str = Field(..., description="⽤户名或邮箱")
    password: str = Field(..., description="密码")


class UserBrief(BaseModel):
    """⽤户简要信息（嵌⼊在 Token 响应中）"""
    id: int
    username: str
    email: str
    avatar: Optional[str] = None
    display_language: str = "zh"
    roles: list[str] = []

    model_config = {
        "from_attributes": True,
    }


class TokenResponse(BaseModel):
    """登录成功响应（兼容OAuth2标准格式）"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 1800
    user: UserBrief


# --- ⽤户管理 ---


class UserResponse(BaseModel):
    """⽤户详情响应"""
    id: int
    username: str
    email: str
    phone: Optional[str] = None
    avatar: Optional[str] = None
    display_language: str = "zh"
    is_active: bool
    is_superuser: bool
    roles: list[str] = []
    last_login_at: Optional[datetime] = None
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }


class UserUpdate(BaseModel):
    """⽤户信息更新"""
    phone: Optional[str] = None
    avatar: Optional[str] = None
    email: Optional[str] = Field(
        None,
        pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
    )


class ChangePassword(BaseModel):
    """修改密码"""
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=100, description="新密码")


class ForgotPasswordRequest(BaseModel):
    """忘记密码请求"""
    email: str = Field(
        ...,
        pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
        description="注册邮箱",
        examples=["user@example.com"],
    )


class VerifyCodeRequest(BaseModel):
    """验证码校验请求"""
    email: str = Field(
        ...,
        pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
        description="注册邮箱",
        examples=["user@example.com"],
    )
    code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
        description="6位验证码",
        examples=["123456"],
    )


class ResetPasswordRequest(BaseModel):
    """重置密码请求"""
    email: str = Field(
        ...,
        pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
        description="注册邮箱",
        examples=["user@example.com"],
    )
    code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
        description="6位验证码",
        examples=["123456"],
    )
    new_password: str = Field(..., min_length=6, max_length=100, description="新密码")


class ProfileResponse(BaseModel):
    """个人信息响应（含检测统计）"""
    id: int
    username: str
    email: str
    phone: Optional[str] = None
    avatar: Optional[str] = None
    display_language: str = "zh"
    is_active: bool
    roles: list[str] = []
    last_login_at: Optional[datetime] = None
    created_at: datetime
    detection_stats: Optional["DetectionStatistics"] = None

    model_config = {
        "from_attributes": True,
    }


class ProfileUpdateRequest(BaseModel):
    """修改个人信息请求"""
    phone: Optional[str] = None
    avatar: Optional[str] = None
    email: Optional[str] = Field(
        None,
        pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
    )


class DisplayLanguageUpdate(BaseModel):
    """更新当前登录用户的界面显示语言。"""

    # 与数据库默认值保持一致，拒绝未支持的语言代码。
    display_language: str = Field(..., pattern="^(zh|en)$")


# --- ⻆⾊权限 ---


class RoleResponse(BaseModel):
    """⻆⾊响应"""
    id: int
    name: str
    display_name: str
    description: Optional[str] = None
    is_system: bool
    permissions: list[str] = []   # 权限编码列表
    created_at: datetime

    class Config:
        from_attributes = True


class RoleCreate(BaseModel):
    """创建⻆⾊"""
    name: str = Field(..., min_length=2, max_length=50, description="⻆⾊标识")
    display_name: str = Field(..., description="⻆⾊显示名")
    description: Optional[str] = None
    permission_codes: list[str] = Field(default=[], description="权限编码列表")


class PermissionResponse(BaseModel):
    """权限响应"""
    id: int
    code: str
    name: str
    module: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


# ══════════════════════════════════════════════════════════════
# ⼆、检测业务
# ══════════════════════════════════════════════════════════════


# --- 检测场景 ---


class SceneCreate(BaseModel):
    """创建检测场景"""
    name: str = Field(..., description="场景标识，如 remote_sensing")
    display_name: str = Field(..., description="场景显示名，如 遥感⽬标检测")
    description: Optional[str] = None
    category: str = Field(..., description="分类：agriculture/industry/remote_sensing/medical/traffic")
    class_names: list[str] = Field(..., description="类别列表")
    class_names_cn: Optional[dict[str, str]] = Field(None, description="中⽂名映射")


class SceneResponse(BaseModel):
    """检测场景响应"""
    id: int
    name: str
    display_name: str
    description: Optional[str] = None
    category: str
    class_names: list
    class_names_cn: Optional[dict] = None
    is_active: bool
    default_model: Optional["ModelVersionBrief"] = None
    created_at: datetime

    class Config:
        from_attributes = True


# --- 检测任务 ---


class DetectionTaskResponse(BaseModel):
    """检测任务响应"""
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    user_id: int
    scene_id: int
    scene_name: Optional[str] = None
    model_version_id: Optional[int] = None
    task_type: str
    status: str
    total_images: int
    total_objects: int
    total_inference_time: float
    conf_threshold: float
    iou_threshold: float
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

class DetectionResultResponse(BaseModel):
    """单条检测结果响应"""
    id: int
    task_id: int
    image_path: str
    annotated_image_url: Optional[str] = None
    class_name: str
    class_name_cn: Optional[str] = None
    class_id: int
    confidence: float
    bbox: list   # [x1, y1, x2, y2]
    inference_time: Optional[float] = None
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DetectionTaskDetail(BaseModel):
    """检测任务详情（含结果列表）"""
    task: DetectionTaskResponse
    results: list[DetectionResultResponse] = []


SeverityRiskLevel = Literal[
    "low",
    "moderate",
    "high",
    "critical",
    "insufficient_information",
]
SeverityAssessmentConfidence = Literal["low", "medium", "high"]


class SeverityAssessmentRequest(BaseModel):
    """病害严重程度评估请求。"""

    class_name: str = Field(..., min_length=1, max_length=100, description="要评估的检测类别")
    answers: dict = Field(default_factory=dict, description="用户问卷答案")
    additional_notes: Optional[str] = Field(None, max_length=1000, description="补充说明")


class SeverityAssessmentResult(BaseModel):
    """严重程度评估结构化输出；规则或 LLM 结果入库前都必须符合该结构。"""

    risk_level: SeverityRiskLevel
    assessment_confidence: SeverityAssessmentConfidence
    summary: str = Field(..., min_length=1, max_length=2000)
    reasons: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class SeverityAssessmentResponse(BaseModel):
    """病害严重程度评估响应。"""

    id: int
    task_id: int
    class_name: str
    class_name_display: Optional[str] = None
    risk_level: SeverityRiskLevel
    assessment_confidence: SeverityAssessmentConfidence
    summary: str
    reasons: list[str]
    uncertainties: list[str]
    recommended_actions: list[str]
    llm_model: Optional[str] = None
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }


class TreatmentStatusUpdate(BaseModel):
    """用户维护治疗状态请求。"""

    status: str = Field(
        ...,
        pattern="^(pending|in_progress|monitoring|treated|resolved)$",
        description="治疗状态",
    )
    note: Optional[str] = Field(None, max_length=1000, description="治疗备注")


class DetectionTaskLocationUpdate(BaseModel):
    """检测任务地理位置更新请求。"""

    latitude: float = Field(..., ge=-90, le=90, description="纬度，建议由前端授权定位后传入")
    longitude: float = Field(..., ge=-180, le=180, description="经度，建议由前端授权定位后传入")
    location_name: Optional[str] = Field(None, max_length=255, description="地点名称")
    location_source: str = Field(
        "manual",
        pattern="^(browser|manual|exif|other)$",
        description="位置来源",
    )


# --- 检测统计 ---


class DetectionStatistics(BaseModel):
    """检测统计数据"""
    total_tasks: int
    total_images: int
    total_objects: int
    avg_inference_time: float
    class_distribution: dict[str, int]   # 各类别检测次数
    daily_trend: list[dict]              # 每⽇检测趋势
    scene_distribution: dict[str, int]   # 各场景检测次数


# ══════════════════════════════════════════════════════════════
# 三、模型管理
# ══════════════════════════════════════════════════════════════


# --- 训练任务 ---


class TrainingTaskCreate(BaseModel):
    """创建训练任务"""
    model_config = ConfigDict(protected_namespaces=())

    scene_id: int = Field(..., description="关联场景 ID")
    model_name: str = Field(default="yolov11n", description="基础模型")
    epochs: int = Field(default=100, ge=10, le=500, description="训练轮数")
    img_size: int = Field(default=640, description="图像尺⼨")
    batch_size: int = Field(default=16, ge=1, le=64, description="批次⼤⼩")
    device: str = Field(default="0", description="训练设备")
    optimizer: str = Field(default="SGD", description="优化器")
    lr0: float = Field(default=0.01, description="初始学习率")
    augment_config: Optional[dict] = Field(None, description="数据增强配置")


class TrainingTaskResponse(BaseModel):
    """训练任务响应"""
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    user_id: int
    scene_id: int
    scene_name: Optional[str] = None
    task_uuid: str
    status: str
    model_name: str
    epochs: int
    current_epoch: int
    progress: int
    img_size: int
    batch_size: int
    device: str
    dataset_size: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class TrainingMetricResponse(BaseModel):
    """训练指标响应（单 epoch）"""
    epoch: int
    box_loss: Optional[float] = None
    cls_loss: Optional[float] = None
    dfl_loss: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    map50: Optional[float] = None
    map50_95: Optional[float] = None
    lr: Optional[float] = None

    class Config:
        from_attributes = True


# --- 模型版本 ---


class ModelVersionBrief(BaseModel):
    """模型版本简要信息"""
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    version: str
    model_name: str
    model_type: str
    map50: Optional[float] = None
    is_default: bool
    created_at: datetime

class ModelVersionResponse(BaseModel):
    """模型版本详情"""
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    scene_id: int
    scene_name: Optional[str] = None
    training_task_id: Optional[int] = None
    version: str
    model_name: str
    model_type: str
    status: str
    model_path: str
    minio_url: Optional[str] = None
    map50: Optional[float] = None
    map50_95: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    per_class_ap: Optional[dict] = None
    description: Optional[str] = None
    file_size: Optional[int] = None
    is_default: bool
    created_at: datetime

class ModelVersionCreate(BaseModel):
    """⼿动上传模型版本"""
    model_config = ConfigDict(protected_namespaces=())

    scene_id: int
    version: str = Field(..., description="版本号")
    model_name: str = Field(..., description="模型名称")
    model_type: str = Field(default="yolov11n", description="模型类型")
    description: Optional[str] = None

# --- 模型评估与导出 ---

class ModelValidateRequest(BaseModel):
    """模型评估请求"""
    split: str = Field(default="val", description="评估数据集划分: val / test / train")
    conf: float = Field(default=0.001, description="置信度阈值")
    iou: float = Field(default=0.6, description="NMS IoU 阈值")


class ModelExportRequest(BaseModel):
    """模型导出请求"""
    version: Optional[str] = Field(None, description="版本号（如 v1.0.0，不传则自动生成）")
    description: Optional[str] = Field(None, description="版本描述/变更说明")
    set_default: bool = Field(default=False, description="是否设为该场景的默认模型")
    upload_minio: bool = Field(default=True, description="是否上传到 MinIO")


class ModelExportResponse(BaseModel):
    """模型导出响应"""
    model_config = ConfigDict(protected_namespaces=())

    model_version_id: int
    version: str
    model_name: str
    model_path: str
    export_dir: str
    minio_url: Optional[str] = None
    file_size: Optional[int] = None
    evaluation: dict
    is_default: bool
    message: str


class ModelValidateResponse(BaseModel):
    """模型评估响应"""
    model_config = ConfigDict(protected_namespaces=())

    task_id: int
    task_uuid: str
    split: str
    overall: dict
    per_class: dict
    model_version_id: Optional[int] = None
    model_version: Optional[str] = None


# ══════════════════════════════════════════════════════════════
# 四、智能体对话
# ══════════════════════════════════════════════════════════════


class ChatSessionCreate(BaseModel):
    """创建对话会话"""
    title: Optional[str] = None


class ChatSessionResponse(BaseModel):
    """对话会话响应"""
    id: int
    session_uuid: str
    title: Optional[str] = None
    status: str
    message_count: int
    last_message_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatMessageRequest(BaseModel):
    """发送消息请求"""
    session_id: Optional[int] = Field(None, description="会话 ID（为空则⾃动创建新会话）")
    content: str = Field(..., min_length=1, max_length=5000, description="消息内容")


class ChatMessageResponse(BaseModel):
    """对话消息响应"""
    id: int
    session_id: int
    role: str
    content: str
    agent_used: Optional[str] = None
    tool_calls: Optional[list] = None
    tool_result: Optional[str] = None
    tokens_used: Optional[int] = None
    latency_ms: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatHistoryResponse(BaseModel):
    """对话历史响应（含会话信息和消息列表）"""
    session: ChatSessionResponse
    messages: list[ChatMessageResponse] = []


# ══════════════════════════════════════════════════════════════
# 五、数据集管理
# ══════════════════════════════════════════════════════════════


class DatasetCreate(BaseModel):
    """创建数据集"""
    name: str = Field(..., description="数据集名称")
    display_name: str = Field(..., description="显示名称")
    description: Optional[str] = None
    category: str = Field(default="agriculture", description="分类")
    format_type: str = Field(default="yolo", description="格式: yolo/voc/coco")


class DatasetResponse(BaseModel):
    """数据集响应"""
    id: int
    name: str
    display_name: str
    description: Optional[str] = None
    category: str
    status: str
    total_images: int
    total_labels: int
    total_classes: int
    class_names: Optional[list] = None
    class_names_cn: Optional[dict] = None
    class_distribution: Optional[dict] = None
    train_count: int
    val_count: int
    test_count: int
    data_size: int
    format_type: str
    label_quality: Optional[float] = None
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DatasetImageResponse(BaseModel):
    """数据集图片响应"""
    id: int
    dataset_id: int
    image_name: str
    image_path: str
    image_url: Optional[str] = None
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    file_size: Optional[int] = None
    has_label: bool
    label_count: int
    split_type: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class DatasetLabelResponse(BaseModel):
    """数据集标签响应"""
    id: int
    dataset_id: int
    image_id: int
    class_id: int
    class_name: str
    class_name_cn: Optional[str] = None
    bbox_x: float
    bbox_y: float
    bbox_width: float
    bbox_height: float
    bbox_x1: Optional[int] = None
    bbox_y1: Optional[int] = None
    bbox_x2: Optional[int] = None
    bbox_y2: Optional[int] = None
    confidence: Optional[float] = None

    class Config:
        from_attributes = True


class DatasetStatistics(BaseModel):
    """数据集统计信息"""
    total_images: int
    total_labels: int
    total_classes: int
    class_distribution: dict[str, int]
    train_count: int
    val_count: int
    test_count: int
    data_size: int
    label_quality: float


class DatasetSplitRequest(BaseModel):
    """数据集划分请求"""
    train_ratio: float = Field(default=0.7, ge=0.5, le=0.9)
    val_ratio: float = Field(default=0.2, ge=0.05, le=0.3)


class DiseaseClassResponse(BaseModel):
    """病害类别响应"""
    class_id: int
    class_name: str
    class_name_cn: str
    sample_count: int = 0


# ══════════════════════════════════════════════════════════════
# 六、知识库管理
# ══════════════════════════════════════════════════════════════


class KnowledgeDocumentResponse(BaseModel):
    """知识库文档响应"""
    id: int
    title: str
    file_path: str
    uploader_id: int
    uploader_name: Optional[str] = None
    status: str
    reviewer_id: Optional[int] = None
    reviewer_name: Optional[str] = None
    review_comment: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    visibility: str
    chunk_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
    }


class KnowledgeDocumentCreate(BaseModel):
    """创建知识库文档（上传时使用）"""
    title: str = Field(..., description="文档标题")


class KnowledgeDocumentApprove(BaseModel):
    """审核通过请求"""
    pass


class KnowledgeDocumentReject(BaseModel):
    """驳回请求"""
    review_comment: str = Field(..., description="驳回原因")


class KnowledgeDocumentQuery(BaseModel):
    """文档查询参数"""
    status: Optional[str] = None
    uploader_id: Optional[int] = None


# ══════════════════════════════════════════════════════════════
# 七、系统运维
# ══════════════════════════════════════════════════════════════


class OperationLogResponse(BaseModel):
    """操作⽇志响应"""
    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    module: str
    action: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    description: Optional[str] = None
    ip_address: Optional[str] = None
    request_method: Optional[str] = None
    request_path: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ══════════════════════════════════════════════════════════════
# 六、通⽤模型
# ══════════════════════════════════════════════════════════════


class ApiResponse(BaseModel):
    """统⼀ API 响应"""
    code: int = 200
    message: str = "success"
    data: Optional[dict | list] = None


class PageParams(BaseModel):
    """分⻚查询参数"""
    page: int = Field(default=1, ge=1, description="⻚码")
    page_size: int = Field(default=20, ge=1, le=100, description="每⻚数量")


class PageResponse(BaseModel):
    """分⻚响应"""
    total: int
    page: int
    page_size: int
    total_pages: int
    items: list


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = "healthy"
    app_name: str
    version: str
    database: Optional[str] = None
    redis: Optional[str] = None
    minio: Optional[str] = None


# 解决前向引用
ProfileResponse.model_rebuild()
