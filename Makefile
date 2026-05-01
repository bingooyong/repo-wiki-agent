PYTHON ?= python3
CONFIG ?=

define RUN
$(PYTHON) -m repo_wiki.main $(1) $(if $(CONFIG),--config $(CONFIG),)
endef

.PHONY: ai-init ai-index ai-update ai-sync ai-verify ai-cost

ai-init:
	$(call RUN,init)

ai-index:
	$(call RUN,index)

ai-update:
	$(call RUN,update)

ai-sync:
	$(call RUN,sync)

ai-verify:
	$(call RUN,verify --ci)

ai-cost:
	$(call RUN,cost-estimate)
