UV ?= uv
PY := $(UV) run python
CHROME ?=
TEMPLATES := templates/style.css templates/document.html.j2 templates/guide.html.j2 templates/sheet.html.j2

.PHONY: all build pdf lint format test audit verify clean

all: build verify
	@echo
	@echo "Open the guide, or print it to PDF from any browser (US Letter, default margins):"
	@echo "  file://$(CURDIR)/dice_tables.html"
	@echo "Optional: 'make pdf' snapshots dice_tables.pdf if a Chromium browser is installed."

build: dice_tables.html

dice_tables.html: generate_dice_tables.py bip39_english.txt $(TEMPLATES)
	$(PY) generate_dice_tables.py

lint:
	$(UV) run ruff check .

format:
	$(UV) run ruff format .

test:
	$(UV) run pytest -q

audit: dice_tables.html
	$(PY) audit_dice_tables.py

verify: lint test audit

# Optional, best-effort: snapshot dice_tables.pdf via a Chromium browser if one is installed.
pdf: dice_tables.html
	@browser="$(CHROME)"; \
	if [ -z "$$browser" ]; then \
	  for b in "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
	           "/Applications/Chromium.app/Contents/MacOS/Chromium" \
	           "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" \
	           "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"; do \
	    [ -x "$$b" ] && browser="$$b" && break; \
	  done; \
	fi; \
	if [ -n "$$browser" ] && [ -x "$$browser" ]; then \
	  "$$browser" --headless --disable-gpu --no-pdf-header-footer \
	    --print-to-pdf="$(CURDIR)/dice_tables.pdf" "$(CURDIR)/dice_tables.html" && \
	  echo "wrote $(CURDIR)/dice_tables.pdf"; \
	else \
	  echo "No Chromium browser found. Open dice_tables.html in any browser and Save as PDF (US Letter, default margins)."; \
	fi

clean:
	rm -rf __pycache__ .venv
