import ReactMarkdown from "react-markdown";

export function Markdown({ content }: { content: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown
        skipHtml
        disallowedElements={["img"]}
        urlTransform={(url) =>
          /^(https?:\/\/|mailto:|\/(?!\/)|#)/i.test(url) ? url : ""
        }
        components={{
          a: ({ children, href }) => (
            <a
              href={href || undefined}
              target={href?.startsWith("http") ? "_blank" : undefined}
              rel="noopener noreferrer"
            >
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

export function Highlight({ text }: { text: string }) {
  return (
    <>
      {text
        .split(/(\ue000[^\ue001]*\ue001)/g)
        .map((part, index) =>
          part.startsWith("\ue000") ? (
            <mark key={index}>{part.slice(1, -1)}</mark>
          ) : (
            <span key={index}>{part.replace(/[\ue000\ue001]/g, "")}</span>
          ),
        )}
    </>
  );
}
