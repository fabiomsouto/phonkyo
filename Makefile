SHELL := bash
.ONESHELL: 

RELEASE ?= v0.1

.PHONY: bundle
bundle:
	zip -r $(RELEASE).zip production/$(RELEASE) 

clean:
	rm *.zip