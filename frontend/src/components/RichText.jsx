import React, { useCallback, useEffect } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Link from "@tiptap/extension-link";
import DOMPurify from "dompurify";
import { Bold, Italic, List, ListOrdered, Link2, Heading2, Heading3 } from "lucide-react";
import "./richtext.css";

export const isEmptyHtml = (html) => {
  if (!html) return true;
  const text = String(html).replace(/<[^>]*>/g, "").replace(/&nbsp;/g, " ").trim();
  return text === "" && !/<img|<hr|<br\s*\/?>(?!\s*$)/i.test(String(html));
};

const sanitize = (html) =>
  DOMPurify.sanitize(String(html || ""), { ADD_ATTR: ["target", "rel"] });

// Read-only render of stored HTML (plain text renders fine too).
export function RichTextView({ html, className = "", placeholder = "—", testId }) {
  if (isEmptyHtml(html)) {
    return <p data-testid={testId} className={className}>{placeholder}</p>;
  }
  return (
    <div
      data-testid={testId}
      className={`rich-content ${className}`}
      dangerouslySetInnerHTML={{ __html: sanitize(html) }}
    />
  );
}

function ToolbarBtn({ onClick, active, label, children, testId }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      data-testid={testId}
      onMouseDown={(e) => e.preventDefault()}
      onClick={onClick}
      className={`p-2 rounded min-h-[36px] min-w-[36px] flex items-center justify-center transition-colors ${
        active ? "bg-blue-900 text-white" : "text-slate-600 hover:bg-slate-200"
      }`}
    >
      {children}
    </button>
  );
}

export function RichTextEditor({ value, onChange, testId }) {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({ heading: { levels: [2, 3] }, link: false }),
      Link.configure({
        openOnClick: false,
        autolink: true,
        HTMLAttributes: { target: "_blank", rel: "noopener noreferrer nofollow" },
      }),
    ],
    content: value || "",
    onUpdate: ({ editor }) => {
      const html = editor.getHTML();
      onChange(isEmptyHtml(html) ? "" : html);
    },
    editorProps: {
      attributes: {
        class: "rich-content ProseMirror-editor focus:outline-none min-h-[96px] px-3 py-2",
        ...(testId ? { "data-testid": testId } : {}),
      },
    },
  });

  // Keep editor in sync if the underlying value is replaced externally (e.g., reload).
  useEffect(() => {
    if (!editor) return;
    const current = editor.getHTML();
    const incoming = value || "";
    if ((isEmptyHtml(current) ? "" : current) !== (isEmptyHtml(incoming) ? "" : incoming)) {
      editor.commands.setContent(incoming, false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, editor]);

  const setLink = useCallback(() => {
    if (!editor) return;
    const prev = editor.getAttributes("link").href || "";
    const url = window.prompt("Enter link URL (leave blank to remove):", prev);
    if (url === null) return;
    if (url.trim() === "") {
      editor.chain().focus().extendMarkRange("link").unsetLink().run();
      return;
    }
    let href = url.trim();
    if (!/^https?:\/\//i.test(href) && !href.startsWith("mailto:")) href = "https://" + href;
    editor.chain().focus().extendMarkRange("link").setLink({ href }).run();
  }, [editor]);

  if (!editor) return null;

  return (
    <div
      className="rich-editor border-2 border-slate-300 rounded-lg overflow-hidden bg-white"
      data-testid={testId ? `${testId}-wrap` : undefined}
    >
      <div className="flex flex-wrap items-center gap-1 border-b border-slate-200 bg-slate-50 px-2 py-1">
        <ToolbarBtn testId={testId && `${testId}-h2`} label="Heading" active={editor.isActive("heading", { level: 2 })} onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}><Heading2 className="w-4 h-4" /></ToolbarBtn>
        <ToolbarBtn testId={testId && `${testId}-h3`} label="Subheading" active={editor.isActive("heading", { level: 3 })} onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}><Heading3 className="w-4 h-4" /></ToolbarBtn>
        <span className="w-px h-5 bg-slate-300 mx-1" />
        <ToolbarBtn testId={testId && `${testId}-bold`} label="Bold" active={editor.isActive("bold")} onClick={() => editor.chain().focus().toggleBold().run()}><Bold className="w-4 h-4" /></ToolbarBtn>
        <ToolbarBtn testId={testId && `${testId}-italic`} label="Italic" active={editor.isActive("italic")} onClick={() => editor.chain().focus().toggleItalic().run()}><Italic className="w-4 h-4" /></ToolbarBtn>
        <span className="w-px h-5 bg-slate-300 mx-1" />
        <ToolbarBtn testId={testId && `${testId}-bullet`} label="Bullet list" active={editor.isActive("bulletList")} onClick={() => editor.chain().focus().toggleBulletList().run()}><List className="w-4 h-4" /></ToolbarBtn>
        <ToolbarBtn testId={testId && `${testId}-ordered`} label="Numbered list" active={editor.isActive("orderedList")} onClick={() => editor.chain().focus().toggleOrderedList().run()}><ListOrdered className="w-4 h-4" /></ToolbarBtn>
        <span className="w-px h-5 bg-slate-300 mx-1" />
        <ToolbarBtn testId={testId && `${testId}-link`} label="Insert link" active={editor.isActive("link")} onClick={setLink}><Link2 className="w-4 h-4" /></ToolbarBtn>
      </div>
      <EditorContent editor={editor} />
    </div>
  );
}
