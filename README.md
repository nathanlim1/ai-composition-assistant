# ai-composition-assistant

Final project for CSC481. Implementation of composition using a knowledge-based AI MIDI composition assistant.

To use the project, make sure you create a `.env` file in the main directory with your `OPENAI_API_KEY`.

---

### Newest Agent Approach:
```
input
   ▼
dynamic_rule_builder
   ▼
composer_planner   (plain-text instruction)
   ▼
handler_agent      (ReAct + MIDI tools)
   ├── if duration < target  →  composer_planner   (keep composing)
   └── else                  →  reviewer_planner
                                   ▼
                               handler_agent  (apply fixes)
                                   ├── more fixes? → reviewer_planner
                                   └── empty prompt → END
```
