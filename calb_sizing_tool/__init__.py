# Compatibility helpers for the package
# Monkeypatch docx OxmlElement.xpath to accept a `namespaces` keyword
# which some tests call; newer/older docx/lxml combos may not accept
# the `namespaces` keyword on the xpath method.
try:
    from docx.oxml import BaseOxmlElement
    from lxml import etree

    _orig_xpath = BaseOxmlElement.xpath

    def _xpath_compat(self, path, *args, **kwargs):
        try:
            # try to call the original xpath; if it accepts kwargs this will succeed
            return _orig_xpath(self, path, *args, **kwargs)
        except TypeError:
            # fallback: if namespaces kw present, use lxml.etree to evaluate
            namespaces = kwargs.get("namespaces")
            if namespaces is not None:
                tree = etree.ElementTree(self)
                return tree.xpath(path, namespaces=namespaces)
            # otherwise try original without kwargs
            return _orig_xpath(self, path, *args)

    BaseOxmlElement.xpath = _xpath_compat
except Exception:
    # Best-effort only; if this fails we still continue without the patch
    pass
