# Git 完全入门教程

> 目标：从零开始，学完就能正常使用 Git 管理代码

---

## 一、Git 是什么

Git 是一个**版本控制工具**——帮你记录文件的每一次修改，随时可以回退到任意历史版本。

可以理解为文件的"时光机"。

---

## 二、安装

### macOS（你已经安装了）
```bash
git --version    # 检查是否已安装
```

### 首次使用：设置你的名字和邮箱
```bash
git config --global user.name "你的名字"
git config --global user.email "你的邮箱"
```

---

## 三、核心概念（先搞懂再动手）

Git 文件有三种状态：

```
工作区（你编辑的文件）
    │
    ▼  git add
暂存区（准备提交的文件）
    │
    ▼  git commit
本地仓库（永久保存的历史）
    │
    ▼  git push
远程仓库（GitHub 等云端）
```

- **工作区** → 你当前看到和编辑的文件
- **暂存区** → 标记"我要提交这些改动"
- **提交** → 把暂存的改动永久保存为一个历史快照
- **远程** → 把提交推送到云端，与他人共享

---

## 四、从零开始 —— 完整工作流

### 第 1 步：创建/克隆仓库

**方式 A：已有远程仓库，克隆到本地**
```bash
git clone https://github.com/用户名/仓库名.git
cd 仓库名
```

**方式 B：本地项目，初始化为仓库**
```bash
cd 你的项目目录
git init
```

### 第 2 步：查看当前状态
```bash
git status
```
这是你**最常用**的命令。它会告诉你：
- 哪些文件被修改了
- 哪些文件是新加的
- 哪些文件已经暂存

### 第 3 步：把文件加入暂存区
```bash
# 添加单个文件
git add 文件名.txt

# 添加整个目录
git add src/

# 添加所有改动
git add .
```

### 第 4 步：提交（保存快照）
```bash
git commit -m "添加用户登录功能"
```

提交信息规范：
- 用现在时，简短描述做了什么
- ✅ `git commit -m "添加用户登录功能"`
- ✅ `git commit -m "修复首页图片不显示"`
- ❌ `git commit -m "改了一点点东西"`（太模糊）

### 第 5 步：推送到远程
```bash
# 首次推送（关联远程分支）
git push -u origin main

# 后续推送
git push
```

### 第 6 步：拉取别人的更新
```bash
git pull
```

---

## 五、日常开发流程（真实场景）

### 场景 1：开发新功能（推荐做法）

```bash
# 1. 确保在最新状态
git checkout main
git pull

# 2. 创建新分支（功能隔离）
git checkout -b feature/login-page

# 3. 正常工作：写代码 → 查看状态 → 暂存 → 提交
git status
git add .
git commit -m "实现用户登录页面"

git add .
git commit -m "添加登录表单验证"

# 4. 推送到远程
git push -u origin feature/login-page

# 5. 在 GitHub 上创建 Pull Request
```

### 场景 2：更新主分支

```bash
# 切回主分支
git checkout main

# 拉取远程最新代码
git pull

# 合并功能分支
git merge feature/login-page

# 推送更新
git push
```

### 场景 3：修改了代码，想撤销

```bash
# 撤销工作区的修改（未 git add）
git restore 文件名.txt

# 撤销暂存（已 git add，但还没 commit）
git restore --staged 文件名.txt

# 撤销最近一次提交（已 commit，但还没 push）
git reset --soft HEAD~1
```

### 场景 4：查看历史

```bash
# 查看提交历史
git log

# 查看简洁历史
git log --oneline

# 查看图形化历史
git log --oneline --graph --all

# 查看某个文件的修改历史
git log -p 文件名.txt
```

### 场景 5：对比改动

```bash
# 查看工作区与暂存区的差异
git diff

# 查看暂存区与最近提交的差异
git diff --staged

# 查看两个分支的差异
git diff main..feature/login-page
```

---

## 六、分支操作

### 基本命令

```bash
# 查看所有分支
git branch

# 创建分支
git branch feature/new-page

# 切换分支
git checkout feature/new-page
# 或者（新版）
git switch feature/new-page

# 创建并切换（最常用）
git checkout -b feature/new-page

# 删除已合并的分支
git branch -d feature/new-page

# 强制删除未合并的分支
git branch -D feature/new-page
```

### 合并分支

```bash
# 切到目标分支
git checkout main

# 合并功能分支
git merge feature/new-page
```

如果有冲突，Git 会提示你。打开冲突文件，找到 `<<<<<<<` 和 `>>>>>>>` 标记，手动解决后：
```bash
git add 冲突文件.txt
git commit -m "解决合并冲突"
```

---

## 七、远程仓库操作

### 添加远程仓库
```bash
git remote add origin https://github.com/用户名/仓库名.git
```

### 查看所有远程仓库
```bash
git remote -v
```

### 推送
```bash
# 推送到远程 main 分支
git push origin main

# 首次推送（建立跟踪关系）
git push -u origin main
```

### 拉取
```bash
# 拉取并合并
git pull origin main

# 只拉取不合并（fetch）
git fetch origin
```

### 克隆
```bash
git clone https://github.com/用户名/仓库名.git
git clone https://github.com/用户名/仓库名.git 自定义目录名
```

---

## 八、实用技巧

### .gitignore —— 忽略不需要的文件

在项目根目录创建 `.gitignore` 文件，写入不想跟踪的文件模式：

```
# 依赖目录
node_modules/
vendor/

# 编译产物
dist/
build/
*.pyc

# 环境变量
.env
.env.local

# IDE 配置
.vscode/
.idea/

# 系统文件
.DS_Store
Thumbs.db
```

### 别名 —— 少打字
```bash
git config --global alias.st "status"
git config --global alias.co "checkout"
git config --global alias.br "branch"
git config --global alias.ci "commit"
git config --global alias.lg "log --oneline --graph --all"

# 使用
git st      # = git status
git co main # = git checkout main
git lg      # = git log --oneline --graph --all
```

### 查看某一行是谁写的
```bash
git blame 文件名.txt
```

### 临时保存当前工作（不提交）
```bash
git stash          # 保存当前改动
git stash list     # 查看保存列表
git stash pop      # 恢复最近一次保存
```

---

## 九、常见错误和解决

### 问题：`fatal: Not a git repository`
→ 你没在 git 仓库目录里。先 `cd` 到正确目录，或者运行 `git init`。

### 问题：`Merge conflict`
→ 两个分支改了同一行。打开文件手动解决，然后 `git add` + `git commit`。

### 问题：`Please tell me who you are`
→ 没设置用户名和邮箱。运行：
```bash
git config --global user.name "你的名字"
git config --global user.email "你的邮箱"
```

### 问题：`Updates were rejected because the remote contains work`
→ 远程有新提交，你需要先 `git pull` 再 `git push`。

### 问题：误删了文件
```bash
git checkout -- 文件名      # 恢复未 add 的删除
git reset HEAD 文件名       # 恢复已 add 的删除
git restore 文件名          # 新版通用恢复命令
```

---

## 十、速查表（贴墙上）

| 命令 | 作用 |
|------|------|
| `git status` | 查看当前状态 |
| `git add .` | 添加所有改动 |
| `git commit -m "消息"` | 提交快照 |
| `git push` | 推送到远程 |
| `git pull` | 拉取远程更新 |
| `git log --oneline` | 查看历史 |
| `git diff` | 查看改动 |
| `git checkout -b 分支名` | 创建并切换分支 |
| `git merge 分支名` | 合并分支 |
| `git restore 文件` | 撤销修改 |

---

## 十一、推荐学习路径

1. **先动手**：按第四节的 6 步走一遍，别光看
2. **每天用**：把 Git 当成日常工具，不用记所有命令
3. **遇到问题再查**：不用一次学完，用到哪个学哪个
4. **推荐资源**：
   - 交互式学习：[Learn Git Branching](https://learngitbranching.js.org/)（可视化，强烈推荐）
   - 官方手册：https://git-scm.com/book/zh/v2（中文版）
   - 备忘清单：搜索 "Git cheat sheet"
