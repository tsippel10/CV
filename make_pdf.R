# Quarto post-render hook: print the rendered HTML to PDF with headless Chrome
# so CV_Sippel.pdf is visually identical to CV.html (same CSS, cards, colors, layout).
pagedown::chrome_print(
  input = "CV.html",
  output = "CV_Sippel.pdf",
  options = list(
    printBackground = TRUE, # keep card/heading background colors and borders
    preferCSSPageSize = TRUE,
    displayHeaderFooter = FALSE # drop Chrome's title/date header and URL footer
  )
)
