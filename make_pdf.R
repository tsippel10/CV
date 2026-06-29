# Quarto post-render hook: print the rendered HTML to PDF with headless Chrome
# so PDF.pdf is visually identical to CV.html (same CSS, cards, colors, layout).
pagedown::chrome_print(
  input  = "CV.html",
  output = "PDF.pdf",
  options = list(
    printBackground   = TRUE,  # keep card/heading background colors and borders
    preferCSSPageSize = TRUE
  )
)
