VENV		:= .venv
PYTHON		:= $(VENV)/bin/python
PIP			:= $(PYTHON) -m pip
MAIN		:= a_maze_ing.py
CONFIG		:= config.txt

MLX_URL		:= https://cdn.intra.42.fr/document/document/56307/mlx-2.2.tgz
MLX_DIR		:= .mlx
MLX_TGZ		:= $(MLX_DIR)/mlx-2.2.tgz
# checks if the distro is fedora/rhel or fedora/rhel-like
# quiet grep, checking if the ID= or ID_LIKE= configs have fedora or rhel in them
MLX_DISTRO	:= $(shell grep -qiE '^ID(_LIKE)?=.*(fedora|rhel)' /etc/os-release 2>/dev/null \
				   && echo fedora || echo ubuntu)
MLX_WHL		:= $(MLX_DIR)/$(MLX_DISTRO)/mlx-2.2-py3-none-any.whl

FLAKE8_EXCLUDE	:= .git,.claude,__pycache__,$(VENV),build,dist
MYPY_FLAGS		:= --warn-return-any --warn-unused-ignores \
				   --ignore-missing-imports --disallow-untyped-defs \
				   --check-untyped-defs

.PHONY: all install mlx run debug clean fclean lint lint-strict build

all: install

$(PYTHON):
	python3 -m venv $(VENV)

install: $(PYTHON) mlx
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

mlx: $(PYTHON) $(MLX_WHL)
	$(PIP) install $(MLX_WHL)

$(MLX_TGZ):
	mkdir -p $(MLX_DIR)
	curl -fsSL -o $@ $(MLX_URL)

$(MLX_WHL): $(MLX_TGZ)
	tar -xzmf $< -C $(MLX_DIR) $(MLX_DISTRO)/mlx-2.2-py3-none-any.whl

run:
	$(PYTHON) $(MAIN) $(CONFIG)

debug:
	$(PYTHON) -m pdb $(MAIN) $(CONFIG)

clean:
	find . -path ./$(VENV) -prune -o -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf .mypy_cache .pytest_cache build dist *.egg-info

fclean: clean
	rm -f mazegen-*.whl mazegen-*.tar.gz
	rm -rf $(MLX_DIR)

lint:
	$(PYTHON) -m flake8 . --exclude $(FLAKE8_EXCLUDE)
	$(PYTHON) -m mypy . $(MYPY_FLAGS)

lint-strict:
	$(PYTHON) -m flake8 . --exclude $(FLAKE8_EXCLUDE)
	$(PYTHON) -m mypy . --strict

build:
	$(PYTHON) -m build --outdir .
	rm -rf build *.egg-info
