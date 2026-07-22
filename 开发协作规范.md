# AgriAgent-Disease-System

基于多智能体协同的果蔬病害检测与智能防治系统

## 开发协作规范

为了保证项目代码质量和多人协作效率，本项目采用 GitHub Pull Request 工作流程。

---

### 首次加入项目（只执行一次）
1. 进入项目目录
```bash
cd 项目目录
```
2. 初始化 Git
```bash
git init
```
3. 连接仓库
```bash
git remote add origin https://github.com/beishengyixiao0-rgb/AgriAgent-Disease-System.git
```

4. 检查是否成功：
```bash
git remote -v
```
应该看到：
```
origin  https://github.com/beishengyixiao0-rgb/AgriAgent-Disease-System.git (fetch)
origin  https://github.com/beishengyixiao0-rgb/AgriAgent-Disease-System.git (push)
```
5. 获取仓库最新代码
```bash
git fetch origin
```
6. 覆盖同名文件
```bash
git checkout origin/main -- .
```

结果：
| 文件情况 | 处理结果 |
| ---- | ---- |
| 仓库里存在，本地也有 | 用仓库版本覆盖 |
| 仓库里存在，本地没有 | 下载到本地 |
| 仓库没有，本地有 | 保留 |

7. 建立本地`main`分支并关联远程`main`
```bash
git checkout -b main origin/main
```

以上流程只执行一次。

拉取后可以重新执行以下命令
```bash
cd frontend
npm install

cd backend
.venv\Scripts\activate
pip install -r requirements.txt
```

### 1. 分支管理

项目主分支：

- `main`：稳定版本分支，仅用于发布和保存经过审核的代码。
- `分工+名字`：个人开发分支，个人所有的提交都在这个分支。

**禁止直接向 `main` 分支提交代码。**

分支命名建议：以`分工+名字`命名。

例如：
```
backend-yourusername   # 后端
frontend-yourusername  # 前端
deploy-youusername     # 部署
```

---


### 2. 开发流程
 
#### （1）拉取最新代码
开始新功能开发前，请先同步主分支：

1. 切换到主分支
```bash
git checkout main  
```

2. 拉取远程仓库 main 分支的所有新增提交
```bash
git pull origin main
```

#### （2）创建个人开发分支

创建并切换到自己的个人分支：

```bash
git checkout -b 分工+名字
```
这里只创建一次，后续直接切换(两次命令不同)：

例如：
```bash
git checkout backend-yourusername  
```
切换到自己的分支后：

**1. 把 main 合并进自己的分支**
```bash
git merge main
```

**2. 更新数据库结构**

```bash
cd backend
.venv\Scripts\activate
alembic upgrade head
```

查看当前在哪个分支:
```bash
git branch
```


#### （3）进行代码开发

完成代码修改后：

```bash
git add .
git commit -m "完成xxx功能"
```
提交信息建议简洁明确，例如：

```
完成用户登录功能
修复模型预测错误
优化数据处理流程
```

注意：

- `commit` 只会保存到本地仓库，不会上传到 GitHub；
- 已经`commit`的修改不会因为切换到`main`分支并执行`git pull`而被覆盖；
- **开发过程中建议及时进行`commit`**，保存阶段性成果，避免长时间积累未提交修改。


#### （4）推送个人分支

将自己的分支推送到 GitHub：

```bash
git push origin 分工+名字
```

例如：

```bash
git push origin backend-yourusername 
```

注意不要执行：

```bash
git push origin main
```
直接推送主分支会被仓库规则拒绝。


---

### 3. 提交 Pull Request

代码推送成功后：

1. 进入 GitHub 仓库页面；
2. 点击 `Pull requests`；
3. 点击 `New pull request`；
4. 选择：

base:`main`

compare:`backend-yourusername `

5. 填写 Pull Request 标题和说明；
6. 点击 `Create pull request`。

示例：

标题：`完成用户登录模块`

描述：

```
本次修改内容：
- 添加登录接口
- 增加用户验证逻辑
- 修复异常输入问题
```

---

### 4. 代码审核与合并

Pull Request 创建后，由负责人进行代码审核。

负责人会：

* 检查代码实现；
* 检查代码规范；
* 测试功能是否正常；
* 提出修改意见。

1. 审核通过后负责人点击：`Approve`,然后：`Merge pull request`,代码合并进入 `main`。
2. 需要修改时负责人选择：`Request changes`,开发成员根据意见修改代码：

```bash
git add .
git commit -m "根据review修改"
git push origin backend-yourusername 
```

原 Pull Request 会自动更新，无需重新创建。

---

### 5. 注意事项

- 禁止直接修改 `main` 分支；
- **提交代码前确保项目可以正常运行，完成功能测试**；
- Commit 信息应清晰描述修改内容；
- 不要提交无关文件（例如编译生成文件、临时文件等）。
