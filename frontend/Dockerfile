 # =============================================================
 # 前端 — 多阶段构建 (Node → Nginx alpine)
 # 最终镜像约 ~20MB
 # =============================================================

 # ---- 构建阶段 ----
 FROM node:20-alpine AS build

 WORKDIR /app

 COPY package*.json ./
 RUN npm ci

 COPY . .

 # 构建时设置 API 前缀为 /api（由 Nginx 反向代理）
 ARG VITE_API_BASE_URL=/api
 ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

 RUN npm run build


 # ---- 运行阶段 ----
 FROM nginx:alpine

 # 将构建产物复制到 Nginx 静态目录
 COPY --from=build /app/dist /usr/share/nginx/html

 # 替换 Nginx 默认配置
 COPY nginx.conf /etc/nginx/conf.d/default.conf

 EXPOSE 80

 CMD ["nginx", "-g", "daemon off;"]
