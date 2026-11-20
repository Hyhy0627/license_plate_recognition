# ==========================================
# Dockerfile cho Frontend ALPR System (Next.js)
# ==========================================
FROM node:20-alpine AS base

WORKDIR /app

# Cài đặt dependencies
COPY package.json package-lock.json ./
RUN npm ci

# Copy toàn bộ mã nguồn frontend
COPY . .

# Build Next.js application
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production
ENV HOSTNAME="0.0.0.0"
ENV PORT=3000
RUN npm run build

EXPOSE 3000

# Khởi chạy Next.js production server
CMD ["npm", "run", "start"]
