all

# Rules can be configured. See https://github.com/markdownlint/markdownlint/blob/master/docs/RULES.md

# See https://github.com/markdownlint/markdownlint/blob/master/docs/RULES.md#md026---trailing-punctuation-in-header
rule 'MD026', :punctuation => '.,;:!'

exclude_rule 'MD009' # Trailing spaces (common error frustrates users)
exclude_rule 'MD013' # Line length (breaking lines in paragraphs produces longer diffs)
exclude_rule 'MD024' # Multiple headers with the same content (bug https://github.com/markdownlint/markdownlint/issues/175)
exclude_rule 'MD033' # Inline HTML (some files require HTML)
