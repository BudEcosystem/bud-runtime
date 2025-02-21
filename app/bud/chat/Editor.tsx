/**
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 *
 */

import { AutoFocusPlugin } from "@lexical/react/LexicalAutoFocusPlugin";
import { LexicalComposer } from "@lexical/react/LexicalComposer";
import { ContentEditable } from "@lexical/react/LexicalContentEditable";
import { LexicalErrorBoundary } from "@lexical/react/LexicalErrorBoundary";
import { HistoryPlugin } from "@lexical/react/LexicalHistoryPlugin";
import { RichTextPlugin } from "@lexical/react/LexicalRichTextPlugin";
import { OnChangePlugin } from "@lexical/react/LexicalOnChangePlugin";
import {
  $isTextNode,
  DOMConversionMap,
  DOMExportOutput,
  DOMExportOutputMap,
  isHTMLElement,
  Klass,
  LexicalEditor,
  LexicalNode,
  ParagraphNode,
  TextNode,
} from "lexical";
import ToolbarPlugin from "../../plugin/ToolbarPlugin";
import { ChatRequestOptions } from "ai";
import { Image } from "antd";

const MIN_ALLOWED_FONT_SIZE = 8;
const MAX_ALLOWED_FONT_SIZE = 72;

export const parseAllowedFontSize = (input: string): string => {
  const match = input.match(/^(\d+(?:\.\d+)?)px$/);
  if (match) {
    const n = Number(match[1]);
    if (n >= MIN_ALLOWED_FONT_SIZE && n <= MAX_ALLOWED_FONT_SIZE) {
      return input;
    }
  }
  return "";
};

export function parseAllowedColor(input: string) {
  return /^rgb\(\d+, \d+, \d+\)$/.test(input) ? input : "";
}

const placeholder = "Enter some rich text...";

const removeStylesExportDOM = (
  editor: LexicalEditor,
  target: LexicalNode
): DOMExportOutput => {
  const output = target.exportDOM(editor);
  if (output && isHTMLElement(output.element)) {
    // Remove all inline styles and classes if the element is an HTMLElement
    // Children are checked as well since TextNode can be nested
    // in i, b, and strong tags.
    for (const el of [
      output.element,
      ...output.element.querySelectorAll('[style],[class],[dir="ltr"]'),
    ]) {
      el.removeAttribute("class");
      el.removeAttribute("style");
      if (el.getAttribute("dir") === "ltr") {
        el.removeAttribute("dir");
      }
    }
  }
  return output;
};

const exportMap: DOMExportOutputMap = new Map<
  Klass<LexicalNode>,
  (editor: LexicalEditor, target: LexicalNode) => DOMExportOutput
>([
  [ParagraphNode, removeStylesExportDOM],
  [TextNode, removeStylesExportDOM],
]);

const getExtraStyles = (element: HTMLElement): string => {
  // Parse styles from pasted input, but only if they match exactly the
  // sort of styles that would be produced by exportDOM
  let extraStyles = "";
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

const constructImportMap = (): DOMConversionMap => {
  const importMap: DOMConversionMap = {};

  // Wrap all TextNode importers with a function that also imports
  // the custom styles implemented by the playground
  for (const [tag, fn] of Object.entries(TextNode.importDOM() || {})) {
    importMap[tag] = (importNode) => {
      const importer = fn(importNode);
      if (!importer) {
        return null;
      }
      return {
        ...importer,
        conversion: (element) => {
          const output = importer.conversion(element);
          if (
            output === null ||
            output.forChild === undefined ||
            output.after !== undefined ||
            output.node !== null
          ) {
            return output;
          }
          const extraStyles = getExtraStyles(element);
          if (extraStyles) {
            const { forChild } = output;
            return {
              ...output,
              forChild: (child, parent) => {
                const textNode = forChild(child, parent);
                if ($isTextNode(textNode)) {
                  textNode.setStyle(textNode.getStyle() + extraStyles);
                }
                return textNode;
              },
            };
          }
          return output;
        },
      };
    };
  }

  return importMap;
};

const editorConfig = {
  html: {
    export: exportMap,
    import: constructImportMap(),
  },
  namespace: "React.js Demo",
  nodes: [ParagraphNode, TextNode],
  onError(error: Error) {
    throw error;
  },
  theme: {
    code: "editor-code",
    heading: {
      h1: "editor-heading-h1",
      h2: "editor-heading-h2",
      h3: "editor-heading-h3",
      h4: "editor-heading-h4",
      h5: "editor-heading-h5",
    },
    image: "editor-image",
    link: "editor-link",
    list: {
      listitem: "editor-listitem",
      nested: {
        listitem: "editor-nested-listitem",
      },
      ol: "editor-list-ol",
      ul: "editor-list-ul",
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
      underlineStrikethrough: "editor-text-underlineStrikethrough",
    },
  },
};

interface EditorProps {
  input: string;
  handleInputChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  handleSubmit: (
    event?: {
      preventDefault?: () => void;
    },
    chatRequestOptions?: ChatRequestOptions
  ) => void;
}

export default function Editor(props: EditorProps) {
  return (
    <div className="flex flex-row w-full  fixed left-0 bottom-0 justify-center items-center mb-[.5rem] bg-[#101010]">
      <form className="chat-message-form max-w-2xl  w-full  flex items-center justify-center  border-t-2 rounded-[0.625rem] relative z-10">
        <div className="blur-[0.5rem] absolute top-0 left-0 right-0 bottom-0 bg-[#FFFFFF03] rounded-[0.5rem] " />
        <LexicalComposer initialConfig={editorConfig}>
          <div className="editor-container">
            <ToolbarPlugin />
            <OnChangePlugin
              onChange={(editorState, editor) => {
                const data = editorState.toJSON() as any;
                const children = data?.root?.children?.[0]?.children as any;
                console.log(children[0]?.text);
                props.handleInputChange({
                  target: { value: children[0]?.text } as any,
                } as any);
              }}
            />
            <div className="editor-inner">
              <RichTextPlugin
                contentEditable={
                  <ContentEditable
                    value={props.input}
                    className="editor-input"
                    name="editor"
                    aria-placeholder={placeholder}
                    placeholder={
                      <div className="editor-placeholder">{placeholder}</div>
                    }
                  />
                }
                ErrorBoundary={LexicalErrorBoundary}
              />
              <HistoryPlugin />
              <AutoFocusPlugin />
            </div>
          </div>
        </LexicalComposer>
        <button
          className="z-[999] absolute text-[#EEEEEE30] border-[#757575] border-[1px] rounded-[0.5rem] p-[.5rem] hover:bg-[#1F1F1F4D] hover:text-[#FFF] right-[0.5rem] bottom-[0.5rem] flex items-center gap-[.5rem]"
          type="button"
          onClick={props.handleSubmit}
        >
          Send
          <Image src="icons/send.svg" alt="send" preview={false} />
        </button>
      </form>
    </div>
  );
}
