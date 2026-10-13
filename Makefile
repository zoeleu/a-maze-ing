# The Python to use, as a command: python3 (the default), python3.13, pypy3,
# a path... e.g. `make PY=pypy3 test`. Each one gets its own virtual
# environment, since a venv only works with the interpreter that made it:
# .venv for python3, .venv-<name> for the others.
PY			?= python3
VENV		?= $(if $(filter python3,$(PY)),.venv,.venv-$(notdir $(PY)))
PYTHON		:= $(VENV)/bin/python
PIP			:= $(PYTHON) -m pip
# written once the dependencies are installed, so the targets that need
# them can install them first, for whichever Python is chosen
INSTALLED	:= $(VENV)/.installed
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

# .venv* covers the virtual environments of every Python
FLAKE8_EXCLUDE	:= .git,.claude,__pycache__,.venv*,build,dist
MYPY_FLAGS		:= --warn-return-any --warn-unused-ignores \
				   --ignore-missing-imports --disallow-untyped-defs \
				   --check-untyped-defs

.PHONY: all install mlx run debug test clean fclean lint lint-strict build \
		python

all: install

$(PYTHON):
	@command -v $(PY) >/dev/null 2>&1 || { \
		echo "error: no '$(PY)' command; pick another with PY=..." >&2; \
		exit 1; }
	@# a failed venv can leave bin/python behind, which would pass for a
	@# working environment next time
	$(PY) -m venv $(VENV) || { rm -rf $(VENV); exit 1; }

install: $(INSTALLED)

$(INSTALLED): requirements.txt $(MLX_WHL) | $(PYTHON)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install $(MLX_WHL)
	touch $@

mlx: $(PYTHON) $(MLX_WHL)
	$(PIP) install $(MLX_WHL)

$(MLX_TGZ):
	mkdir -p $(MLX_DIR)
	curl -fsSL -o $@ $(MLX_URL)

$(MLX_WHL): $(MLX_TGZ)
	tar -xzmf $< -C $(MLX_DIR) $(MLX_DISTRO)/mlx-2.2-py3-none-any.whl

# which interpreter and environment the other targets use
python: | $(PYTHON)
	@echo "$(PY) -> $(VENV)"
	@$(PYTHON) -c 'import platform, sys; print(platform.python_implementation(), platform.python_version(), "at", sys.executable)'

run: $(INSTALLED)
	$(PYTHON) $(MAIN) $(CONFIG)

debug: $(INSTALLED)
	$(PYTHON) -m pdb $(MAIN) $(CONFIG)

test: $(INSTALLED)
	$(PYTHON) -m pytest

clean:
	find . -path './.venv*' -prune -o -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf .mypy_cache .pytest_cache build dist *.egg-info

fclean: clean
	rm -f mazegen-*.whl mazegen-*.tar.gz
	rm -rf $(MLX_DIR)

lint: $(INSTALLED)
	$(PYTHON) -m flake8 . --exclude '$(FLAKE8_EXCLUDE)'
	$(PYTHON) -m mypy . $(MYPY_FLAGS)

lint-strict: $(INSTALLED)
	$(PYTHON) -m flake8 . --exclude '$(FLAKE8_EXCLUDE)'
	$(PYTHON) -m mypy . --strict

build: $(INSTALLED)
	$(PYTHON) -m build --outdir .
	rm -rf build *.egg-info
