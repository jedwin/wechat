# 写在最前面：强烈建议先阅读官方教程[Dockerfile最佳实践]（https://docs.docker.com/develop/develop-images/dockerfile_best-practices/）
# 选择构建用基础镜像（选择原则：在包含所有用到的依赖前提下尽可能提及小）。如需更换，请到[dockerhub官方仓库](https://hub.docker.com/_/python?tab=tags)自行选择后替换。

# 选择基础镜像
# FROM alpine:3.13
FROM python:3.9-slim-bullseye

# 选用国内镜像源以提高下载速度
# RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.tencent.com/g' /etc/apk/repositories
# 替换阿里云的源
# RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories
# RUN echo "http://mirrors.aliyun.com/alpine/latest-stable/main/" > /etc/apk/repositories
# RUN echo "http://mirrors.aliyun.com/alpine/latest-stable/community/" >> /etc/apk/repositories
# RUN apk update
# RUN apk add --update --no-cache python3 py3-pip python3-dev gcc musl-dev postgresql-dev uwsgi uwsgi-plugin-python3
# 容器默认时区为UTC，如需使用上海时间请启用以下时区设置命令
# RUN apk add tzdata && cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && echo Asia/Shanghai > /etc/timezone

# 使用 HTTPS 协议访问容器云调用证书安装
# RUN apk add ca-certificates
# RUN rm -rf /var/cache/apk/*


# For debian
# RUN touch /etc/apt/sources.list
RUN sed -i "s@http://\(deb\|security\).debian.org@https://mirrors.tencent.com@g" /etc/apt/sources.list
RUN apt update && apt install -y uwsgi uwsgi-plugin-python3 locales
RUN sed -i -e 's/# zh_CN.UTF-8 UTF-8/zh_CN.UTF-8 UTF-8/' /etc/locale.gen
RUN dpkg-reconfigure --frontend=noninteractive locales

# 拷贝当前项目requirments.txt到/app目录下
COPY . /app
COPY requirements.txt /tmp

# 设定当前的工作目录
WORKDIR /app

# 安装依赖到指定的/install文件夹
# 选用国内镜像源以提高下载速度
RUN pip config set global.index-url http://mirrors.cloud.tencent.com/pypi/simple
RUN pip config set global.trusted-host mirrors.cloud.tencent.com
# RUN pip install --upgrade pip
# pip install scipy 等数学包失败，可使用 apk add py3-scipy 进行， 参考安装 https://pkgs.alpinelinux.org/packages?name=py3-scipy&branch=v3.13
RUN pip install --user -r /tmp/requirements.txt

# 设定对外端口
EXPOSE 80

# 对模型进行migrate
# RUN python3 manage.py makemigrations
# RUN python3 manage.py migrate
# 设定启动命令
CMD ["python3", "manage.py", "runserver", "0.0.0.0:80"]
# CMD ["uwsgi", "--ini", "uwsgi_setting.ini"]