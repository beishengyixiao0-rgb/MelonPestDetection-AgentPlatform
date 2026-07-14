API接口说明
一、后端整体模块划分
模块 1：用户权限模块
管理账号登录、权限、个人任务隔离，所有检测 / 训练数据绑定用户 ID
模块 2：数据集管理模块
水果病虫害数据集上传、格式转换、划分、预览、存储（MinIO）
模块 3：模型训练模块
YOLOv11 训练任务创建、进度监控、超参数配置、模型评估、模型版本管理
模块 4：病虫害检测服务模块
单图 / 批量 / 文件夹 / 视频 / 摄像头五类检测逻辑，结果入库、结果图 MinIO 存储
模块 5：历史与统计看板模块
检测记录查询、筛选、病虫害统计、趋势图表数据接口
模块 6：智能体 Agent 工具模块
LangGraph 多智能体工具封装：检测工具、历史查询工具、病虫害问答工具
模块 7：RAG 病虫害知识库模块
水果病害文本上传、向量化、检索问答（匹配智能体对话）
模块 8：公共基础设施模块
日志、全局异常、健康检查、Docker 资源、MinIO 文件通用接口


模块 1 用户权限模块
接口路径	       请求方式	    接口功能	        请求参数	              返回说明
/auth/register	   POST	       用户注册	    username,password,group_id	 用户 ID、token
/auth/login	       POST	       登录获取    JWT	username,password	  access_token、用户信息
/auth/info         GET	       获取当前登录用户	Header 带 Token	        用户基础信息、所属小组
/auth/logout	   POST	       退出登录	            Token	              清除 Redis 会话


模块 2 水果病虫害数据集管理
2.1 数据集基础操作
接口路径	                    请求方式	                         功能
/dataset/create	                POST	            创建水果数据集，指定水果品类、病虫害类别
/dataset/upload/images	        POST	                上传原图至 MinIO，绑定数据集 ID
/dataset/upload/labels	        POST	                  上传标注文件（VOC/COCO/LabelMe）
/dataset/convert	            POST	               通用格式转 YOLO TXT，自动生成 data.yaml
/dataset/split	                POST	                    划分 train/val/test 8:1:1
/dataset/list	                GET	                        查询当前用户所有水果数据集
/dataset/detail/{dataset_id}	GET	                    数据集详情：图片数量、病害类别、标注完整性
/dataset/preview/{dataset_id}	GET	                        返回带标注框的样本预览图
/dataset/delete/{dataset_id}	DELETE	                   删除数据集 + MinIO 对应文件

2.2 病虫害分类辅助接口
/dataset/disease/class GET：内置水果病虫害分类字典（苹果褐斑病、柑橘溃疡病、草莓白粉病等），前端下拉选择


模块 3 YOLOv11 模型训练模块
接口路径	                        请求方式	                          功能
/training/task/create	            POST	创建训练任务：绑定数据集、配置 epochs/batch/ 学习率、选用 yolov11n/s/m
/training/task/start/{task_id}	    POST	启动后台训练进程
/training/task/status/{task_id}	    GET	    实时获取训练进度、loss、mAP50、当前 epoch
/training/task/log/{task_id}	    GET	    读取 results.csv，返回曲线指标数据
/training/task/eval/{task_id}	    GET	    模型评估：mAP50、Precision、Recall、每类病害 AP、混淆矩阵数据
/training/task/download/{task_id}	GET	    下载 best.pt 最优模型文件
/training/task/list	                GET	    用户训练任务列表（状态：待启动 / 训练中 / 完成 / 失败）
/training/task/stop/{task_id}	    POST	终止训练任务


模块 4 水果病虫害检测核心服务
统一入参通用配置：model_id（选用训练好的病虫害模型）、conf_thresh置信阈值、iou_threshNMS 阈值
 1.   单图检测
/detection/single POST
上传单张水果图片 → 推理识别病虫害 → 结果图存入 MinIO → 记录入库
返回：病害类别、置信度、检测框坐标、结果图 URL
 2.   批量图片检测
/detection/batch POST
多图批量上传，异步批量推理，实时返回每张图检测结果
 3.   本地文件夹检测
/detection/folder POST
传入 MinIO 内数据集文件夹路径，批量遍历推理，生成批量检测报告
 4.   视频病虫害检测
/detection/video POST
上传水果视频，逐帧推理，合成标注结果视频；SSE 推送处理进度
SSE 通道：/detection/video/progress/{task_id}
 5.   摄像头实时检测（WebSocket）
ws://ip:port/api/v1/detection/camera/{model_id}
前端推送摄像头帧 → 后端推理 → 返回带病害标注框的图像流

辅助检测接口
/detection/model/list GET：用户已训练完成的病虫害模型列表，供前端选择
/detection/result/image/{record_id} GET：获取 MinIO 存储的标注结果图


模块 5 检测历史与数据看板
接口路径	                    请求方式	              功能
/history/record/list	         GET	检测记录分页查询，筛选条件：水果品类、病害、时间、模型
/history/record/{record_id}	     GET	单条检测完整详情：目标列表、置信度、原图 / 结果图
/history/stat/disease	         GET	统计各类病虫害检出数量（看板饼图）
/history/stat/trend	             GET	按日期统计检测总量趋势（折线图）
/history/stat/model/compare	     GET	多模型 mAP、检测耗时对比数据


模块 6 LangGraph 智能体 Agent 接口
流式对话主接口（SSE）
/agent/chat/stream POST
入参：用户提问、会话 ID；流式返回 AI 思考过程 + 工具调用结果

内置 3 个 Agent 工具自动路由：
DetectionAgent 工具：自然语言触发检测（例：帮我检测这张草莓图片病害）
AnalysisAgent 工具：查询历史检测统计、模型效果
SuggestionAgent 工具：检测后向用户提供针对性防治建议
QAAgent 工具：检索 RAG 病虫害知识库，返回病害防治方案

辅助接口：
/agent/session/list GET：用户历史对话会话列表
/agent/session/clear/{session_id} POST：清空对话记忆（Redis）


模块 7 RAG 水果病虫害知识库
接口路径	                请求方式	            功能
/knowledge/upload	        POST	上传病害文档（txt/md），自动分块、向量化存入 Pgvector
/knowledge/add	            POST	手动新增病害条目：水果种类、病害名称、症状、防治方法
/knowledge/search	        POST	向量检索相似病害知识，供 Agent 问答调用
/knowledge/list	            GET	    知识库条目管理列表
/knowledge/delete/{id}	    DELETE	删除病害知识库记录


模块 8 公共基础接口
1.健康检查：/health GET
2.MinIO 通用文件上传：/common/upload POST（数据集、图片、视频通用）
3.全局日志接口：/log/api GET（查询系统 API 调用日志）
4.pytest 测试专用：/test/api/all GET（自动化接口测试）

