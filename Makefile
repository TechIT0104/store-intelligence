# Store Intelligence — common tasks. (Linux/macOS/WSL; Windows users: see README.)
.DEFAULT_GOAL := help
.PHONY: help up down logs ps build test detect annotate assertions clean

CLIPS ?= ../CCTV Footage-20260529T160731Z-3-00144614ea/CCTV Footage

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up: ## Build + start the whole stack (acceptance gate)
	docker compose up -d --build

down: ## Stop the stack
	docker compose down

logs: ## Tail API logs
	docker compose logs -f api

ps: ## Show service status
	docker compose ps

build: ## Build images only
	docker compose build

test: ## Run the test suite with coverage
	pytest --cov=app --cov=pipeline --cov-report=term-missing

assertions: ## Run the acceptance assertions against a running stack
	python assertions.py

detect: ## Run detection on the clips -> pipeline/output/events.jsonl
	python -m pipeline.detect --clips-dir "$(CLIPS)" --layout data/store_layout.json \
	  --out pipeline/output/events.jsonl --sample-fps 5 --device $${DEVICE:-cpu}

annotate: ## Render an annotated detection video for one clip (CLIP=CAM\ 2.mp4)
	python -m pipeline.detect --clips-dir "$(CLIPS)" --layout data/store_layout.json \
	  --out pipeline/output/events.jsonl --sample-fps 5 --device $${DEVICE:-cpu} \
	  --annotate --only "$${CLIP:-CAM 2.mp4}"

clean: ## Remove the stack + volumes
	docker compose down -v
