# Zhihu Archive

## 目标

这套脚本用于：
- 登录知乎并保存 token
- 归档指定作者的文章
- 如果个人主页文章抓不全，再按专栏补抓

当前默认作者：`qingyitouzihao`

## 推荐顺序

1. 先运行 `login_zhihu.py`
2. 再运行 `archive_qingyi.py`
3. 如果失败，查看 `outputs\qingyitouzihao\run_log.json`
4. 如果个人主页不全，再让脚本自动按专栏补抓

## 主要文件

- `login_zhihu.py`：登录并保存 token
- `archive_qingyi.py`：抓取作者文章和专栏
- `zhihu_archive_utils.py`：公共函数
- `outputs\qingyitouzihao`：输出目录
