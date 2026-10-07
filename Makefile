# CrewAIFullstackTest: Flask + CrewAI 后端 与 Vue + Vite 前端
# 在仓库根目录执行 make help 查看全部命令，默认目标为 help。
# 首次运行前请先复制 crewaiBackend/.env.example 为 crewaiBackend/.env 并填写模型凭据。

# 可覆盖，例如 make backend PYTHON=python
BASE_PYTHON ?= python
NPM         ?= npm

ifeq ($(OS),Windows_NT)
# Windows 下固定用 cmd 执行，避免从 Git Bash 调用时 sh.exe 改写路径与参数。
SHELL        := cmd.exe
BACKEND_DIR  := crewaiBackend
FRONTEND_DIR := crewaiFrontend
VENV_PYTHON  := $(BACKEND_DIR)\.venv\Scripts\python.exe
else
BACKEND_DIR  := crewaiBackend
FRONTEND_DIR := crewaiFrontend
VENV_PYTHON  := $(BACKEND_DIR)/.venv/bin/python
endif
PYTHON ?= $(VENV_PYTHON)

.DEFAULT_GOAL := help
.PHONY: help install install-backend install-frontend backend frontend dev build

help:
	@echo CrewAIFullstackTest 可用命令
	@echo ----------------------------------------
	@echo make install           安装后端与前端全部依赖
	@echo make install-backend   创建 .venv 并安装 requirements.txt
	@echo make install-frontend  安装前端依赖
	@echo make backend           启动后端 http://127.0.0.1:8012
	@echo make frontend          启动前端 http://localhost:5173
	@echo make dev              新窗口启动后端，当前窗口启动前端
	@echo make build            构建前端生产包
	@echo ----------------------------------------
	@echo 自定义解释器: make backend PYTHON=python

install: install-backend install-frontend

install-backend:
	$(BASE_PYTHON) -m venv $(BACKEND_DIR)/.venv
	"$(PYTHON)" -m pip install -r $(BACKEND_DIR)/requirements.txt

install-frontend:
	$(NPM) --prefix $(FRONTEND_DIR) install

backend:
	"$(PYTHON)" -X utf8 $(BACKEND_DIR)/main.py

frontend:
	$(NPM) --prefix $(FRONTEND_DIR) run dev

ifeq ($(OS),Windows_NT)
dev:
	start "crewai-backend" cmd /k ""$(PYTHON)" -X utf8 $(BACKEND_DIR)/main.py"
	$(NPM) --prefix $(FRONTEND_DIR) run dev
else
dev:
	@echo Windows 之外请分别在两个终端执行 make backend 与 make frontend
endif

build: install-frontend
	$(NPM) --prefix $(FRONTEND_DIR) run build
