import type { AcademicDocument, ChatMessage, Conversation } from "../types";

export const documents: AcademicDocument[] = [
  {
    id: "doc-1",
    name: "Attention Is All You Need.pdf",
    subject: "Machine Learning",
    pages: 15,
    size: "2.4 MB",
    date: "Today",
    status: "Indexed",
    chunks: 48,
    type: "Research paper",
  },
  {
    id: "doc-2",
    name: "Operating Systems: Three Easy Pieces.pdf",
    subject: "Computer Science",
    pages: 684,
    size: "8.1 MB",
    date: "Yesterday",
    status: "Indexed",
    chunks: 1240,
    type: "Textbook",
  },
  {
    id: "doc-3",
    name: "Database System Concepts — Ch. 3.pdf",
    subject: "Database Systems",
    pages: 58,
    size: "4.2 MB",
    date: "Sep 24, 2026",
    status: "Indexed",
    chunks: 112,
    type: "Course notes",
  },
  {
    id: "doc-4",
    name: "Deep Residual Learning for Image Recognition.pdf",
    subject: "Machine Learning",
    pages: 10,
    size: "1.8 MB",
    date: "Sep 22, 2026",
    status: "Processing",
    chunks: 0,
    type: "Research paper",
  },
  {
    id: "doc-5",
    name: "Linear Algebra and Its Applications.pdf",
    subject: "Mathematics",
    pages: 412,
    size: "6.5 MB",
    date: "Sep 18, 2026",
    status: "Indexed",
    chunks: 816,
    type: "Textbook",
  },
  {
    id: "doc-6",
    name: "A Survey of Large Language Models.pdf",
    subject: "Machine Learning",
    pages: 42,
    size: "3.1 MB",
    date: "Sep 15, 2026",
    status: "Failed",
    chunks: 0,
    type: "Research paper",
  },
];

const transformerSource = {
  documentId: "doc-1",
  document: "Attention Is All You Need.pdf",
  page: 3,
  excerpt:
    "The Transformer follows this overall architecture using stacked self-attention and point-wise, fully connected layers for both the encoder and decoder.",
  relevance: 98,
};

const osSource = {
  documentId: "doc-2",
  document: "Operating Systems: Three Easy Pieces.pdf",
  page: 42,
  excerpt:
    "The OS virtualizes the CPU, memory, and I/O devices, turning physical resources into a set of more powerful, easy-to-use virtual forms.",
  relevance: 94,
};

const seedMessages: ChatMessage[] = [
  {
    id: "msg-1",
    role: "user",
    timestamp: "9:41 AM",
    content:
      "How does the Transformer architecture replace recurrence in sequence modeling?",
  },
  {
    id: "msg-2",
    role: "assistant",
    timestamp: "9:41 AM",
    content:
      "The Transformer replaces recurrence with **self-attention**, allowing each position to directly attend to every other position in the sequence. This makes the computation parallelizable while still modeling long-range relationships.",
    sources: [transformerSource],
  },
];

export const conversations: Conversation[] = [
  {
    id: "chat-1",
    title: "Transformer architecture",
    updated: "9:41 AM",
    messages: seedMessages,
  },
  {
    id: "chat-2",
    title: "Process scheduling algorithms",
    updated: "Yesterday",
    messages: [],
  },
  {
    id: "chat-3",
    title: "Relational normalization",
    updated: "Sep 25",
    messages: [],
  },
];

export function mockAnswer(question: string) {
  const normalized = question.toLowerCase();
  if (/operating system|virtualiz|cpu|memory|process/.test(normalized)) {
    return {
      answer:
        "The operating system abstracts physical hardware into manageable resources. In the provided text, the OS is described as virtualizing the CPU, memory, and I/O devices, making them easier for applications to use.",
      sources: [osSource],
      confidence: 0.94,
    };
  }
  if (/transformer|attention|recurr|sequence/.test(normalized)) {
    return {
      answer:
        "The Transformer models relationships between tokens with **self-attention** rather than recurrence. Each token can attend to all other tokens in a single layer, so sequences can be processed in parallel while capturing long-range dependencies.",
      sources: [transformerSource],
      confidence: 0.98,
    };
  }
  if (/database|normal|sql|relational/.test(normalized)) {
    return {
      answer:
        "The retrieved material describes relational database concepts, but does not contain enough directly relevant text to support a detailed answer to this question.",
      sources: [],
      confidence: 0.2,
    };
  }
  return {
    answer: "Information not found in the provided documents.",
    sources: [],
    confidence: 0,
  };
}
