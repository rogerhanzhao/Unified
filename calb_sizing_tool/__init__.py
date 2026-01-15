# -----------------------------------------------------------------------------
# Personal Open-Source Notice
#
# Copyright (c) 2026 Alex.Zhao. All rights reserved.
#
# This repository is released under the MIT License (see LICENSE file).
# Intended use: learning, evaluation, and engineering reference for Utility-scale
# BESS/ESS sizing and Reporting workflows.
#
# DISCLAIMER: This software is provided "AS IS", without warranty of any kind,
# express or implied. In no event shall the author(s) be liable for any claim,
# damages, or other liability arising from, out of, or in connection with the
# software or the use or other dealings in the software.
#
# NOTE: This is a personal project. It is not an official product or statement
# of any company or organization.
# -----------------------------------------------------------------------------

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
