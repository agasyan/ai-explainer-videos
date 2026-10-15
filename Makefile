export HOST_UID := $(shell id -u)
export HOST_GID := $(shell id -g)
# Only these values may come from the command line. Any other (EV=, SHELL=, MAKEFLAGS=) could replace a recipe.
ARGS := SLUG TITLE STEP FORMAT PART SCENE FILE MODEL SAMPLE
$(foreach v,$(.VARIABLES),$(if $(filter command line,$(origin $(v))),$(if $(filter $(v),$(ARGS)),,$(error $(v)= is not an option here. Options: $(ARGS)))))
# A dashboard job runs with EV_JOB_SLUG set to its one video. make keeps only the last SLUG= it is given, so this
# check, not the command text, stops `SLUG=dns SLUG=other` (or SLUG+=) from reaching another video.
$(if $(EV_JOB_SLUG),$(if $(filter-out $(EV_JOB_SLUG),$(value SLUG)),$(error This job works on $(EV_JOB_SLUG), not $(value SLUG))))
# One target per run: make runs every target it is given, so `make status approve` would approve with no prompt.
$(if $(word 2,$(MAKECMDGOALS)),$(error Run one target at a time, not: $(MAKECMDGOALS)))
# compose.yaml only: no compose.override.yaml, no .env.
COMPOSE = docker compose -f compose.yaml --env-file /dev/null
EV   = $(COMPOSE) run --rm -T ev
# Every value from the command line reaches the shell as one single-quoted word, never as code.
# $(value X) keeps make from running a $(shell ...) hidden in X; q quotes it for sh.
q    = '$(subst ','\'',$(value $(1)))'
unexport SLUG TITLE STEP FORMAT PART SCENE FILE MODEL SAMPLE  # make would expand them to export them
V    = 'generated_videos/$(subst ','\'',$(value SLUG))'
OPTS = $(if $(value FORMAT),--format $(call q,FORMAT)) $(if $(value PART),--part $(call q,PART)) $(if $(value SCENE),--scene $(call q,SCENE))

help:       ## List the commands
	@awk -F':.*## ' '/^[a-z]+:.*## /{printf "  %-11s %s\n", $$1, $$2}' Makefile
build:      ## Build the Docker image (once)
	$(COMPOSE) build
doctor:     ## Check every tool inside the image
	$(EV) doctor
test:       ## Run the unit tests (tests/) inside the image
	docker run --rm --network none --user $(HOST_UID):$(HOST_GID) -v "$(CURDIR)":/work:ro ai-explainer-videos test  # read-only: test code cannot write a video or an approval
new:        ## Start a video: make new SLUG=dns TITLE="How DNS works" [SAMPLE=autopilot-training]
	$(EV) new $(call q,SLUG) --title $(call q,TITLE) $(if $(value SAMPLE),--sample $(call q,SAMPLE))
narrate:    ## Step 1: make the voice and write storyboard.md: make narrate SLUG=dns
	$(EV) narrate $(V)
storyboard: ## Rewrite storyboard.md and print it as JSON: make storyboard SLUG=dns
	$(EV) storyboard $(V)
status:     ## Show the steps and the next action: make status SLUG=dns
	$(EV) status $(V)
approve:    ## Approve a step after you check it: make approve SLUG=dns STEP=plan|preview
	$(EV) approve $(V) $(call q,STEP)
auto:       ## Your consent to run to the 720p preview with no plan stop: make auto SLUG=dns
	$(EV) auto $(V)
preview:    ## Step 2: 720p video, review frames, lint: make preview SLUG=dns [FORMAT=story] [SCENE=hook]
	$(EV) render $(V) --quality 720p $(OPTS)
video:      ## Step 3: 1080p video, after the preview is approved: make video SLUG=dns [FORMAT=both]
	$(EV) render $(V) --quality 1080p $(OPTS)
reference:  ## Study a reference video's pacing and look: make reference FILE=ref.mp4
	$(EV) reference $(call q,FILE)
transcribe: ## Speech to text: make transcribe FILE=talk.m4a [MODEL=small]
	$(COMPOSE) run --rm -T ev-online transcribe $(call q,FILE) --model $(if $(value MODEL),$(call q,MODEL),base.en)
catalog:    ## Maintainers: check moodboards and video formats, render swatches, write catalog.json
	docker run --rm --network none --user $(HOST_UID):$(HOST_GID) -v "$(CURDIR)":/work:ro -v "$(CURDIR)/moodboards":/work/moodboards -v "$(CURDIR)/video-formats":/work/video-formats ai-explainer-videos catalog --write
sample:     ## Maintainers, on the host: publish an approved video as videos/samples/<slug>: make sample SLUG=dns
	python3 -I ev/samples.py $(call q,SLUG)
dashboard:  ## Local web page that runs Claude Code jobs
	python3 dashboard/server.py
shell:      ## Open a shell inside the image
	$(COMPOSE) run --rm --entrypoint bash ev

.PHONY: help build doctor test catalog sample new narrate storyboard status approve auto preview video reference transcribe dashboard shell
