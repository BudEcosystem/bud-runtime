"use strict";
/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */
var __assign = (this && this.__assign) || function () {
    __assign = Object.assign || function(t) {
        for (var s, i = 1, n = arguments.length; i < n; i++) {
            s = arguments[i];
            for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p))
                t[p] = s[p];
        }
        return t;
    };
    return __assign.apply(this, arguments);
};
var __spreadArrays = (this && this.__spreadArrays) || function () {
    for (var s = 0, i = 0, il = arguments.length; i < il; i++) s += arguments[i].length;
    for (var r = Array(s), k = 0, i = 0; i < il; i++)
        for (var a = arguments[i], j = 0, jl = a.length; j < jl; j++, k++)
            r[k] = a[j];
    return r;
};
exports.__esModule = true;
exports.parseAllowedColor = exports.parseAllowedFontSize = void 0;
var LexicalAutoFocusPlugin_1 = require("@lexical/react/LexicalAutoFocusPlugin");
var LexicalComposer_1 = require("@lexical/react/LexicalComposer");
var LexicalContentEditable_1 = require("@lexical/react/LexicalContentEditable");
var LexicalErrorBoundary_1 = require("@lexical/react/LexicalErrorBoundary");
var LexicalHistoryPlugin_1 = require("@lexical/react/LexicalHistoryPlugin");
var LexicalRichTextPlugin_1 = require("@lexical/react/LexicalRichTextPlugin");
var lexical_1 = require("lexical");
var ToolbarPlugin_1 = require("./plugin/ToolbarPlugin");
var MIN_ALLOWED_FONT_SIZE = 8;
var MAX_ALLOWED_FONT_SIZE = 72;
exports.parseAllowedFontSize = function (input) {
    var match = input.match(/^(\d+(?:\.\d+)?)px$/);
    if (match) {
        var n = Number(match[1]);
        if (n >= MIN_ALLOWED_FONT_SIZE && n <= MAX_ALLOWED_FONT_SIZE) {
            return input;
        }
    }
    return "";
};
function parseAllowedColor(input) {
    return /^rgb\(\d+, \d+, \d+\)$/.test(input) ? input : "";
}
exports.parseAllowedColor = parseAllowedColor;
var placeholder = "Enter some rich text...";
var removeStylesExportDOM = function (editor, target) {
    var output = target.exportDOM(editor);
    if (output && lexical_1.isHTMLElement(output.element)) {
        // Remove all inline styles and classes if the element is an HTMLElement
        // Children are checked as well since TextNode can be nested
        // in i, b, and strong tags.
        for (var _i = 0, _a = __spreadArrays([
            output.element
        ], output.element.querySelectorAll('[style],[class],[dir="ltr"]')); _i < _a.length; _i++) {
            var el = _a[_i];
            el.removeAttribute("class");
            el.removeAttribute("style");
            if (el.getAttribute("dir") === "ltr") {
                el.removeAttribute("dir");
            }
        }
    }
    return output;
};
var exportMap = new Map([
    [lexical_1.ParagraphNode, removeStylesExportDOM],
    [lexical_1.TextNode, removeStylesExportDOM],
]);
var getExtraStyles = function (element) {
    // Parse styles from pasted input, but only if they match exactly the
    // sort of styles that would be produced by exportDOM
    var extraStyles = "";
    //   const fontSize = parseAllowedFontSize(element.style.fontSize);
    //   const backgroundColor = parseAllowedColor(element.style.backgroundColor);
    //   const color = parseAllowedColor(element.style.color);
    //   if (fontSize !== '' && fontSize !== '15px') {
    //     extraStyles += `font-size: ${fontSize};`;
    //   }
    //   if (backgroundColor !== '' && backgroundColor !== 'rgb(255, 255, 255)') {
    //     extraStyles += `background-color: ${backgroundColor};`;
    //   }
    //   if (color !== '' && color !== 'rgb(0, 0, 0)') {
    //     extraStyles += `color: ${color};`;
    //   }
    return extraStyles;
};
var constructImportMap = function () {
    var importMap = {};
    var _loop_1 = function (tag, fn) {
        importMap[tag] = function (importNode) {
            var importer = fn(importNode);
            if (!importer) {
                return null;
            }
            return __assign(__assign({}, importer), { conversion: function (element) {
                    var output = importer.conversion(element);
                    if (output === null ||
                        output.forChild === undefined ||
                        output.after !== undefined ||
                        output.node !== null) {
                        return output;
                    }
                    var extraStyles = getExtraStyles(element);
                    if (extraStyles) {
                        var forChild_1 = output.forChild;
                        return __assign(__assign({}, output), { forChild: function (child, parent) {
                                var textNode = forChild_1(child, parent);
                                if (lexical_1.$isTextNode(textNode)) {
                                    textNode.setStyle(textNode.getStyle() + extraStyles);
                                }
                                return textNode;
                            } });
                    }
                    return output;
                } });
        };
    };
    // Wrap all TextNode importers with a function that also imports
    // the custom styles implemented by the playground
    for (var _i = 0, _a = Object.entries(lexical_1.TextNode.importDOM() || {}); _i < _a.length; _i++) {
        var _b = _a[_i], tag = _b[0], fn = _b[1];
        _loop_1(tag, fn);
    }
    return importMap;
};
var editorConfig = {
    html: {
        "export": exportMap,
        "import": constructImportMap()
    },
    namespace: "React.js Demo",
    nodes: [lexical_1.ParagraphNode, lexical_1.TextNode],
    onError: function (error) {
        throw error;
    },
    theme: {
        code: "editor-code",
        heading: {
            h1: "editor-heading-h1",
            h2: "editor-heading-h2",
            h3: "editor-heading-h3",
            h4: "editor-heading-h4",
            h5: "editor-heading-h5"
        },
        image: "editor-image",
        link: "editor-link",
        list: {
            listitem: "editor-listitem",
            nested: {
                listitem: "editor-nested-listitem"
            },
            ol: "editor-list-ol",
            ul: "editor-list-ul"
        },
        ltr: "ltr",
        paragraph: "editor-paragraph",
        placeholder: "editor-placeholder",
        quote: "editor-quote",
        rtl: "rtl",
        text: {
            bold: "editor-text-bold",
            code: "editor-text-code",
            hashtag: "editor-text-hashtag",
            italic: "editor-text-italic",
            overflowed: "editor-text-overflowed",
            strikethrough: "editor-text-strikethrough",
            underline: "editor-text-underline",
            underlineStrikethrough: "editor-text-underlineStrikethrough"
        }
    }
};
function Editor() {
    return (React.createElement(LexicalComposer_1.LexicalComposer, { initialConfig: editorConfig },
        React.createElement("div", { className: "editor-container" },
            React.createElement(ToolbarPlugin_1["default"], null),
            React.createElement("div", { className: "editor-inner" },
                React.createElement(LexicalRichTextPlugin_1.RichTextPlugin, { contentEditable: React.createElement(LexicalContentEditable_1.ContentEditable, { className: "editor-input", "aria-placeholder": placeholder, placeholder: React.createElement("div", { className: "editor-placeholder" }, placeholder) }), ErrorBoundary: LexicalErrorBoundary_1.LexicalErrorBoundary }),
                React.createElement(LexicalHistoryPlugin_1.HistoryPlugin, null),
                React.createElement(LexicalAutoFocusPlugin_1.AutoFocusPlugin, null)))));
}
exports["default"] = Editor;
