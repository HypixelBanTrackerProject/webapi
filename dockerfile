# 使用 Python 基础镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY . .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 暴露 FastAPI 默认端口
EXPOSE 8000

VOLUME ["/app/save"]

# 启动应用
CMD ["fastapi","run"]