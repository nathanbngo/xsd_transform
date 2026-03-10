(function () {
  "use strict";

  const xsdText = document.getElementById("xsd-text");
  const xsltText = document.getElementById("xslt-text");
  const btnTransform = document.getElementById("btn-transform");
  const btnClear = document.getElementById("btn-clear");
  const btnCopy = document.getElementById("btn-copy");
  const btnDownload = document.getElementById("btn-download");
  const errorMsg = document.getElementById("error-msg");
  const outputPlaceholder = document.getElementById("output-placeholder");
  const outputPre = document.getElementById("output-pre");
  const outputCode = document.getElementById("output-code");
  const outputMeta = document.getElementById("output-meta");

  const xsdFileInput = document.getElementById("xsd-file");
  const xsltFileInput = document.getElementById("xslt-file");
  const loadXsdBtn = document.getElementById("load-xsd-file");
  const loadXsltBtn = document.getElementById("load-xslt-file");
  const dropXsd = document.getElementById("drop-xsd");
  const dropXslt = document.getElementById("drop-xslt");

  let lastOutputString = "";
  /** @type {string} */
  let lastMime = "application/xml";

  /** Max characters to render in DOM to avoid freezing tab on huge output */
  const OUTPUT_RENDER_LIMIT = 500000;

  function showError(message) {
    errorMsg.textContent = message;
    errorMsg.hidden = false;
  }

  function clearError() {
    errorMsg.hidden = true;
    errorMsg.textContent = "";
  }

  /**
   * Strip UTF-8 BOM and normalize line endings for consistent parsing.
   * @param {string} s
   * @returns {string}
   */
  function normalizeInput(s) {
    if (!s) return s;
    if (s.charCodeAt(0) === 0xfeff) return s.slice(1);
    return s;
  }

  function setOutputMeta(text) {
    if (!outputMeta) return;
    const len = text.length;
    const lines = text ? text.split(/\r\n|\r|\n/).length : 0;
    if (len === 0) {
      outputMeta.textContent = "";
      outputMeta.hidden = true;
    } else {
      outputMeta.textContent =
        lines + " line" + (lines !== 1 ? "s" : "") + " · " + len.toLocaleString() + " characters";
      outputMeta.hidden = false;
    }
  }

  function setOutput(text, mime) {
    lastOutputString = text;
    lastMime = mime || "application/xml";

    if (text.length > OUTPUT_RENDER_LIMIT) {
      outputCode.textContent =
        text.slice(0, OUTPUT_RENDER_LIMIT) +
        "\n\n… truncated for display (" +
        text.length.toLocaleString() +
        " chars total). Download to get the full file.";
    } else {
      outputCode.textContent = text;
    }

    outputPlaceholder.hidden = true;
    outputPre.hidden = false;
    btnCopy.disabled = false;
    btnDownload.disabled = false;
    setOutputMeta(text);
  }

  function clearOutput() {
    lastOutputString = "";
    outputCode.textContent = "";
    outputPlaceholder.hidden = false;
    outputPre.hidden = true;
    btnCopy.disabled = true;
    btnDownload.disabled = true;
    setOutputMeta("");
  }

  /**
   * Parse XML string; throws with label if parse fails.
   * @param {string} xmlString
   * @param {string} label
   * @returns {Document}
   */
  function parseXml(xmlString, label) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(xmlString, "application/xml");
    const err =
      doc.querySelector("parsererror") ||
      doc.getElementsByTagName("parsererror")[0];
    if (err) {
      const text = (err.textContent || "Invalid XML").trim();
      throw new Error(label + ": " + text);
    }
    return doc;
  }

  /**
   * Serialize document/fragment to string.
   * @param {Node} node
   * @returns {string}
   */
  function serializeNode(node) {
    const serializer = new XMLSerializer();
    if (node.nodeType === Node.DOCUMENT_NODE) {
      const de = node.documentElement;
      if (de) return serializer.serializeToString(de);
      const children = node.childNodes;
      let out = "";
      for (let i = 0; i < children.length; i++) {
        out += serializer.serializeToString(children[i]) + "\n";
      }
      return out.trim();
    }
    if (node.nodeType === Node.DOCUMENT_FRAGMENT_NODE) {
      const children = node.childNodes;
      if (children.length === 0) return "";
      let out = "";
      for (let i = 0; i < children.length; i++) {
        out += serializer.serializeToString(children[i]) + "\n";
      }
      return out.trim();
    }
    return serializer.serializeToString(node);
  }

  function setTransforming(busy) {
    btnTransform.disabled = busy;
    btnTransform.classList.toggle("btn-loading", busy);
    if (busy) {
      btnTransform.dataset.label = btnTransform.innerHTML;
      btnTransform.innerHTML =
        '<span class="btn-spinner" aria-hidden="true"></span> Running…';
    } else if (btnTransform.dataset.label) {
      btnTransform.innerHTML = btnTransform.dataset.label;
      delete btnTransform.dataset.label;
    }
  }

  function runTransform() {
    clearError();
    clearOutput();

    if (typeof XSLTProcessor === "undefined") {
      showError(
        "XSLTProcessor is not available in this browser or context. Serve the app over http://localhost (not file://) and use a recent Chrome, Edge, or Firefox."
      );
      return;
    }

    let xsdStr = normalizeInput(xsdText.value);
    let xsltStr = normalizeInput(xsltText.value);

    if (!xsdStr.trim()) {
      showError("Please provide source XML (your XSD content).");
      return;
    }
    if (!xsltStr.trim()) {
      showError("Please provide an XSLT stylesheet.");
      return;
    }

    setTransforming(true);

    function finish() {
      setTransforming(false);
    }

    // Defer so UI can paint loading state
    setTimeout(function () {
      try {
        runTransformSync(xsdStr, xsltStr);
      } finally {
        finish();
      }
    }, 0);
  }

  function runTransformSync(xsdStr, xsltStr) {
    let sourceDoc;
    let xsltDoc;
    try {
      sourceDoc = parseXml(xsdStr, "Source XML");
      xsltDoc = parseXml(xsltStr, "XSLT");
    } catch (e) {
      showError(e.message);
      return;
    }

    const processor = new XSLTProcessor();
    let importOk = true;
    try {
      importOk = processor.importStylesheet(xsltDoc);
    } catch (e) {
      showError("Failed to load stylesheet: " + (e.message || String(e)));
      return;
    }
    // Chromium returns false on failure instead of throwing
    if (importOk === false) {
      showError(
        "Stylesheet was rejected (invalid XSLT 1.0 or unsupported features). Check console for details. XSLT 2.0/3.0 is not supported in the browser."
      );
      return;
    }

    let result;
    try {
      result = processor.transformToDocument(sourceDoc);
    } catch (e) {
      showError("Transform failed: " + (e.message || String(e)));
      return;
    }

    if (!result) {
      showError("Transform returned no document.");
      return;
    }

    const parseErr =
      result.querySelector("parsererror") ||
      result.getElementsByTagName("parsererror")[0];
    if (parseErr) {
      showError(
        "Transform produced invalid XML: " +
          (parseErr.textContent || "").trim()
      );
      return;
    }

    const outStr = serializeNode(result);
    const root = result.documentElement;
    const isHtml =
      root &&
      root.namespaceURI === "http://www.w3.org/1999/xhtml" &&
      root.localName.toLowerCase() === "html";

    if (outStr === "") {
      showError(
        "Transform produced empty output. For text-only results the in-browser engine is limited—ensure your XSLT builds a root element, or use method=\"xml\"/\"html\" with a single root."
      );
      setOutput("", "text/plain");
      return;
    }

    if (isHtml) {
      setOutput(outStr, "text/html");
    } else {
      setOutput(outStr, "application/xml");
    }
  }

  function readFileAsText(file) {
    return new Promise(function (resolve, reject) {
      const reader = new FileReader();
      reader.onload = function () {
        resolve(normalizeInput(String(reader.result || "")));
      };
      reader.onerror = function () {
        reject(reader.error || new Error("Read failed"));
      };
      reader.readAsText(file, "UTF-8");
    });
  }

  function triggerDownload(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.style.display = "none";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () {
      URL.revokeObjectURL(url);
    }, 2500);
  }

  loadXsdBtn.addEventListener("click", function () {
    xsdFileInput.click();
  });
  loadXsltBtn.addEventListener("click", function () {
    xsltFileInput.click();
  });

  xsdFileInput.addEventListener("change", function () {
    const f = xsdFileInput.files && xsdFileInput.files[0];
    if (!f) return;
    readFileAsText(f)
      .then(function (text) {
        xsdText.value = text;
        clearError();
      })
      .catch(function (err) {
        showError("Could not read XSD file: " + (err && err.message ? err.message : "unknown error"));
      });
    xsdFileInput.value = "";
  });

  xsltFileInput.addEventListener("change", function () {
    const f = xsltFileInput.files && xsltFileInput.files[0];
    if (!f) return;
    readFileAsText(f)
      .then(function (text) {
        xsltText.value = text;
        clearError();
      })
      .catch(function (err) {
        showError("Could not read XSLT file: " + (err && err.message ? err.message : "unknown error"));
      });
    xsltFileInput.value = "";
  });

  function setupDropzone(zone, textarea) {
    let dragDepth = 0;
    zone.addEventListener("dragenter", function (e) {
      e.preventDefault();
      dragDepth++;
      zone.classList.add("dragover");
    });
    zone.addEventListener("dragleave", function (e) {
      e.preventDefault();
      dragDepth--;
      if (dragDepth <= 0) {
        dragDepth = 0;
        zone.classList.remove("dragover");
      }
    });
    zone.addEventListener("dragover", function (e) {
      e.preventDefault();
      e.dataTransfer.dropEffect = "copy";
    });
    zone.addEventListener("drop", function (e) {
      e.preventDefault();
      dragDepth = 0;
      zone.classList.remove("dragover");
      const file = e.dataTransfer.files && e.dataTransfer.files[0];
      if (!file) return;
      readFileAsText(file)
        .then(function (text) {
          textarea.value = text;
          clearError();
        })
        .catch(function (err) {
          showError("Could not read dropped file: " + (err && err.message ? err.message : "unknown error"));
        });
    });
  }

  setupDropzone(dropXsd, xsdText);
  setupDropzone(dropXslt, xsltText);

  const SAMPLE_XSD =
    '<?xml version="1.0" encoding="UTF-8"?>\n' +
    '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="http://example.com/ns" xmlns:t="http://example.com/ns" elementFormDefault="qualified">\n' +
    '  <xs:element name="root">\n' +
    "    <xs:complexType>\n" +
    "      <xs:sequence>\n" +
    '        <xs:element name="item" type="xs:string" maxOccurs="unbounded"/>\n' +
    "      </xs:sequence>\n" +
    "    </xs:complexType>\n" +
    "  </xs:element>\n" +
    "</xs:schema>";

  const SAMPLE_XSLT =
    '<?xml version="1.0" encoding="UTF-8"?>\n' +
    '<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">\n' +
    '  <xsl:output method="xml" indent="yes"/>\n' +
    '  <xsl:template match="@*|node()">\n' +
    "    <xsl:copy>\n" +
    '      <xsl:apply-templates select="@*|node()"/>\n' +
    "    </xsl:copy>\n" +
    "  </xsl:template>\n" +
    "</xsl:stylesheet>";

  document.getElementById("btn-sample").addEventListener("click", function () {
    clearError();
    xsdText.value = SAMPLE_XSD;
    xsltText.value = SAMPLE_XSLT;
  });

  btnTransform.addEventListener("click", runTransform);

  btnClear.addEventListener("click", function () {
    xsdText.value = "";
    xsltText.value = "";
    clearError();
    clearOutput();
  });

  btnCopy.addEventListener("click", function () {
    if (!lastOutputString) return;
    if (!navigator.clipboard || !navigator.clipboard.writeText) {
      showError("Clipboard API not available. Select output manually or use Download.");
      return;
    }
    navigator.clipboard.writeText(lastOutputString).then(
      function () {
        var prev = btnCopy.textContent;
        btnCopy.textContent = "Copied!";
        setTimeout(function () {
          btnCopy.textContent = prev;
        }, 1500);
      },
      function () {
        showError("Copy failed. Select output manually or use Download.");
      }
    );
  });

  btnDownload.addEventListener("click", function () {
    if (btnDownload.disabled) return;
    const ext =
      lastMime === "text/html"
        ? "html"
        : lastMime === "text/plain"
          ? "txt"
          : lastMime.includes("text")
            ? "txt"
            : "xml";
    const blob = new Blob([lastOutputString], {
      type: lastMime + ";charset=utf-8",
    });
    triggerDownload(blob, "transform-output." + ext);
  });
})();
