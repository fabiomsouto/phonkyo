SHELL := bash
.ONESHELL: 

RELEASE ?= v0.3

.PHONY: bundle
bundle:
	zip -r $(RELEASE).zip production/$(RELEASE) 

clean:
	rm *.zip