MAIN=main
XELATEX=xelatex -interaction=nonstopmode -halt-on-error

.PHONY: pdf quick clean

pdf:
	$(XELATEX) $(MAIN).tex
	bibtex $(MAIN) || true
	$(XELATEX) $(MAIN).tex
	$(XELATEX) $(MAIN).tex

quick:
	$(XELATEX) $(MAIN).tex

clean:
	rm -f $(MAIN).aux $(MAIN).bbl $(MAIN).bcf $(MAIN).blg $(MAIN).log $(MAIN).out $(MAIN).run.xml $(MAIN).toc $(MAIN).lof $(MAIN).lot
