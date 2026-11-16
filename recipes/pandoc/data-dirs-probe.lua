-- Used by this recipe's test: installed in share/pandoc/filters, it must be
-- found by name through PANDOC_DATA_DIRS (set by pandoc-api's activation).
function Str()
  return pandoc.Str("found")
end
