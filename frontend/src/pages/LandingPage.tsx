import { motion } from "framer-motion";
import {
  ArrowDown,
  ArrowRight,
  BookOpen,
  BrainCircuit,
  Check,
  FileSearch,
  FileText,
  Layers3,
  Play,
  Quote,
  ShieldCheck,
  Sparkles,
  Upload,
  Workflow,
} from "lucide-react";
import { Link } from "react-router-dom";

const features = [
  {
    icon: FileText,
    title: "A library that reads",
    text: "Bring your papers, lecture notes, and textbooks into one searchable academic library.",
  },
  {
    icon: BrainCircuit,
    title: "Answers with receipts",
    text: "Every response is grounded in retrieved passages from the documents you trust.",
  },
  {
    icon: Quote,
    title: "Citations you can follow",
    text: "Jump straight to the source, page, and passage behind any answer.",
  },
  {
    icon: Layers3,
    title: "Ideas across your library",
    text: "Find connections across subjects and documents, not just a single open tab.",
  },
];

export function Brand({ light = false }: { light?: boolean }) {
  return (
    <span className={`brand ${light ? "brand-light" : ""}`}>
      <span className="brand-mark">
        <BookOpen size={17} strokeWidth={2.2} />
      </span>
      <span>
        scholar<span className="brand-dot">.</span>
      </span>
    </span>
  );
}

export function LandingPage() {
  return (
    <main className="landing-page">
      <nav className="landing-nav wrap">
        <Link to="/" aria-label="Scholar home">
          <Brand />
        </Link>
        <div className="landing-links">
          <a href="#features">Why Scholar</a>
          <a href="#how-it-works">How it works</a>
          <a href="#technology">Technology</a>
        </div>
        <div className="landing-actions">
          <Link className="landing-login" to="/login">
            Log in
          </Link>
          <Link className="button button-dark button-sm" to="/register">
            Get started <ArrowRight size={15} />
          </Link>
        </div>
      </nav>

      <section className="landing-hero wrap">
        <motion.div
          className="hero-copy"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55 }}
        >
          <div className="eyebrow">
            <span className="eyebrow-mark">
              <Sparkles size={13} />
            </span>{" "}
            YOUR RESEARCH, IN CONVERSATION
          </div>
          <h1>
            Ask your academic
            <br />
            <em>documents anything.</em>
          </h1>
          <p className="hero-description">
            One thoughtful answer, drawn from the papers you actually read.
            Explore your research library with transparent, page-level
            citations.
          </p>
          <div className="hero-buttons">
            <Link to="/register" className="button button-primary">
              Get started <ArrowRight size={16} />
            </Link>
            <Link to="/login" className="button button-quiet">
              <Play size={14} /> Log in to your workspace
            </Link>
          </div>
          <div className="hero-proof">
            <div className="proof-avatars">
              <span className="proof-symbol">
                <BookOpen size={15} aria-hidden="true" />
              </span>
            </div>
            <span>
              Made for curious minds
              <br />
              <b>and careful researchers</b>
            </span>
            <span className="proof-divider" />
            <span className="proof-lock">
              <ShieldCheck size={16} /> Private by design
            </span>
          </div>
        </motion.div>

        <motion.div
          className="hero-art"
          initial={{ opacity: 0, scale: 0.96, x: 10 }}
          animate={{ opacity: 1, scale: 1, x: 0 }}
          transition={{ duration: 0.7, delay: 0.12 }}
        >
          <div className="art-paper art-paper-back">
            <div />
            <div />
            <div />
            <div />
          </div>
          <div className="art-paper art-paper-front">
            <div className="paper-top">
              <span>RESEARCH NOTE · 03</span>
              <span className="paper-bookmark">
                <BookOpen size={14} />
              </span>
            </div>
            <h2>Attention Is All You Need</h2>
            <p>Vaswani et al. · 2017</p>
            <div className="paper-line paper-line-wide" />
            <div className="paper-line" />
            <div className="paper-line paper-line-mid" />
            <div className="paper-highlight">
              “The Transformer allows for significantly more parallelization...”
            </div>
            <div className="paper-line" />
            <div className="paper-line paper-line-wide" />
          </div>
          <div className="answer-note">
            <div className="answer-note-head">
              <span className="answer-spark">
                <Sparkles size={13} />
              </span>
              <span>Scholar answer</span>
              <span className="answer-conf">Source cited</span>
            </div>
            <p>
              Self-attention lets each token connect directly to every other
              token, replacing recurrence with parallel computation.
            </p>
            <div className="answer-cite">
              <FileSearch size={13} />
              <span>Attention Is All You Need</span>
              <b>p. 3</b>
              <Check size={12} />
            </div>
          </div>
          <span className="art-caption">
            <span /> ANSWERS, GROUNDED IN YOUR READING
          </span>
        </motion.div>
        <a
          className="scroll-cue"
          href="#features"
          aria-label="Scroll to features"
        >
          <ArrowDown size={14} /> A BETTER WAY TO STUDY
        </a>
      </section>

      <section className="landing-features" id="features">
        <div className="wrap">
          <div className="section-intro">
            <span className="section-kicker">BUILT FOR HOW YOU THINK</span>
            <h2>
              More understanding.
              <br />
              <em>Less searching.</em>
            </h2>
          </div>
          <div className="feature-grid">
            {features.map(({ icon: Icon, title, text }, index) => (
              <motion.article
                className="feature-item"
                key={title}
                initial={{ opacity: 0, y: 14 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.08 }}
              >
                <span className="feature-icon">
                  <Icon size={19} />
                </span>
                <h3>{title}</h3>
                <p>{text}</p>
                <span className="feature-index">0{index + 1}</span>
              </motion.article>
            ))}
          </div>
        </div>
      </section>

      <section className="workflow-section wrap" id="how-it-works">
        <div className="workflow-heading">
          <span className="section-kicker">A SIMPLE RESEARCH LOOP</span>
          <h2>
            From reading list
            <br />
            to <em>real insight.</em>
          </h2>
          <p>Your source material stays at the center of every step.</p>
        </div>
        <div className="workflow-steps">
          {[
            { icon: Upload, label: "Upload", text: "Add your PDFs" },
            { icon: Workflow, label: "Process", text: "We index each page" },
            { icon: Sparkles, label: "Ask", text: "Start with a question" },
            {
              icon: FileSearch,
              label: "Retrieve",
              text: "Relevant passages surface",
            },
            { icon: Quote, label: "Understand", text: "Follow cited answers" },
          ].map(({ icon: Icon, label, text }, i) => (
            <div className="workflow-step" key={label}>
              <span className="step-num">0{i + 1}</span>
              <span className={`step-icon step-icon-${i}`}>
                <Icon size={17} />
              </span>
              <b>{label}</b>
              <small>{text}</small>
              {i < 4 && <span className="step-connector" />}
            </div>
          ))}
        </div>
      </section>

      <section className="technology-section" id="technology">
        <div className="wrap technology-inner">
          <div>
            <span className="section-kicker">RIGOR IN, RIGOR OUT</span>
            <h2>
              Useful AI should
              <br />
              show its <em>work.</em>
            </h2>
            <p>
              Scholar combines semantic retrieval with language models, so
              answers start with your material and keep the evidence close.
            </p>
            <Link className="text-link" to="/register">
              Build your research library <ArrowRight size={15} />
            </Link>
          </div>
          <div className="tech-diagram">
            <div>
              <span className="tech-icon tech-source">
                <FileText size={18} />
              </span>
              <b>Your documents</b>
              <small>Private source material</small>
            </div>
            <span className="tech-flow" />
            <div>
              <span className="tech-icon tech-embed">
                <BrainCircuit size={18} />
              </span>
              <b>Semantic retrieval</b>
              <small>Relevant passages found</small>
            </div>
            <span className="tech-flow" />
            <div>
              <span className="tech-icon tech-answer">
                <Quote size={18} />
              </span>
              <b>Grounded answers</b>
              <small>With page citations</small>
            </div>
            <span className="tech-tag">
              <Check size={13} /> Evidence first
            </span>
          </div>
        </div>
      </section>

      <footer className="landing-footer">
        <div className="wrap footer-inner">
          <Link to="/">
            <Brand />
          </Link>
          <span>Thoughtful research starts with a better question.</span>
          <span>© 2026 Scholar AI</span>
        </div>
      </footer>
    </main>
  );
}
