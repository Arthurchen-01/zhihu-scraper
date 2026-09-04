# Zhihu Browser Mode

## 这套方案适合谁

适合你这种：
- Edge / Chrome 已经登录知乎
- 不想再走老旧的 OAuth 登录
- 目标是先尽量把作者文章归档到本地

## 推荐步骤

1. 先关闭正在运行的 Edge 和 Chrome
2. 进入目录：

```powershell
cd C:\Users\25472\projects\zhihu_archive
```

3. 先用 Edge 默认配置跑：

```powershell
python archive_qingyi_browser.py --browser edge --profile Default
```

4. 如果 Edge 不行，再试 Chrome：

```powershell
python archive_qingyi_browser.py --browser chrome --profile Default
```

## 输出位置

- `outputs\qingyitouzihao_browser\articles`
- `outputs\qingyitouzihao_browser\columns`
- `outputs\qingyitouzihao_browser\index`

## 它会做什么

- 打开作者主页
- 收集作者页里的文章链接
- 打开专栏页
- 收集专栏链接
- 进入每个专栏继续补文章链接
- 最后逐篇保存文章内容

## 重要提醒

- 如果浏览器驱动启动失败，优先先关闭 Edge/Chrome 再重试
- 如果知乎页面需要你手工再确认登录，就在弹出的浏览器里确认后再等脚本继续
- 如果文章很多，第一次运行会比较慢
