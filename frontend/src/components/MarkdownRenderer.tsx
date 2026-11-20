import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function normalizeMarkdown(content: string) {
  return content
    .replace(/\r\n?/g, "\n")
    .replace(/[ \t]+(?:-{3,}|_{3,}|\*{3,})[ \t]*(?=#{1,6}(?:\s|$))/g, "\n\n")
    .replace(/^(#{2,6})[ \t]+#[ \t]*(?=\d+[.)]?[ \t])/gm, "$1 ")
    .replace(/(\S)[ \t]+(#{1,6}[ \t]+(?:\d+[.)]?[ \t]*)?[A-Z])/gm, "$1\n\n$2")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export function MarkdownRenderer({ content }: { content: string }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]}>
      {normalizeMarkdown(content)}
    </ReactMarkdown>
  );
}
