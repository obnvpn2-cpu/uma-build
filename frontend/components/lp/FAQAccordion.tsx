"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { faqs } from "./faqs";

export function FAQAccordion() {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  return (
    <div className="space-y-3">
      {faqs.map((faq, i) => (
        <div key={i} className="glass overflow-hidden">
          <button
            onClick={() => setOpenIndex(openIndex === i ? null : i)}
            aria-expanded={openIndex === i}
            aria-controls={`faq-answer-${i}`}
            className="w-full flex items-center justify-between p-6 text-left"
          >
            <span className="font-medium text-text-primary pr-4">
              {faq.q}
            </span>
            <ChevronDown
              className={`w-5 h-5 text-accent shrink-0 transition-transform duration-200 ${
                openIndex === i ? "rotate-180" : ""
              }`}
            />
          </button>
          <div
            id={`faq-answer-${i}`}
            role="region"
            className={`overflow-hidden transition-all duration-200 ${
              openIndex === i ? "max-h-60 opacity-100" : "max-h-0 opacity-0"
            }`}
          >
            <p className="px-6 pb-6 text-sm text-text-secondary leading-relaxed">
              {faq.a}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
