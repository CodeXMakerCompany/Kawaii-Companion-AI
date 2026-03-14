export class AssistantMenuI {
  getList(): any[] {
    return [];
  }
}

export class GitHubMenu extends AssistantMenuI {
  constructor() {
    super();
  }

  getList() {
    return [
      { title: "Create new branch", mcp: "github", input: true, confirmation: true },
      { title: "Create new pr", mcp: "github", input: false, confirmation: true },
      { title: "Check git services", mcp: "github", input: false, confirmation: true },
    ];
  }
}

export class ObsidianMenu extends AssistantMenuI {
  constructor() {
    super();
  }

  getList() {
    return [
      { title: "Create Note", mcp: "obsidian", input: true, confirmation: true },
      { title: "Search Notes", mcp: "obsidian", input: true, confirmation: false },
      { title: "Link Notes", mcp: "obsidian", input: true, confirmation: true },
      { title: "Daily Note", mcp: "obsidian", input: false, confirmation: false },
    ];
  }
}

export class WebMenu extends AssistantMenuI {
  constructor() {
    super();
  }

  getList() {
    return [
      { title: "Open google", mcp: "browser", input: false, confirmation: false },
      { title: "Open brave", mcp: "browser", input: false, confirmation: false },
      { title: "Search keyword", mcp: "browser", input: false, confirmation: false },
      { title: "Search keyword", mcp: "browser", input: false, confirmation: false },
    ];
  }
}

export class SystemMenu extends AssistantMenuI {
  constructor() {
    super();
  }

  getList() {
    return [
      { title: "Open Docker", mcp: "system", input: false, confirmation: false },
      { title: "Open Warp", mcp: "system", input: false, confirmation: false },
      { title: "Open Obsidian", mcp: "system", input: false, confirmation: false },
      { title: "Open Settings", mcp: "system", input: false, confirmation: false },
      { title: "Open Files", mcp: "system", input: false, confirmation: false },
      { title: "Open Mongo", mcp: "system", input: false, confirmation: false },
      { title: "Open DBbeaver", mcp: "system", input: false, confirmation: false },
      { title: "Record Screen", mcp: "system", input: false, confirmation: false },
      { title: "Take a screenshot", mcp: "system", input: false, confirmation: false },
    ];
  }
}

export class AutomationsMenu extends AssistantMenuI {
  constructor() {
    super();
  }

  getList() {
    return [
      { title: "Code Review", mcp: "automation", input: false, confirmation: true },
      { title: "Generate Tests", mcp: "automation", input: true, confirmation: true },
      { title: "Refactor Code", mcp: "automation", input: true, confirmation: true },
      {
        title: "Generate Documentation",
        mcp: "automation",
        input: false,
        confirmation: true,
      },
      {
        title: "Fix Linting Issues",
        mcp: "automation",
        input: false,
        confirmation: false,
      },
      {
        title: "Optimize Performance",
        mcp: "automation",
        input: true,
        confirmation: true,
      },
      { title: "Security Scan", mcp: "automation", input: false, confirmation: false },
      {
        title: "Generate API Endpoints",
        mcp: "automation",
        input: true,
        confirmation: true,
      },
    ];
  }
}

export class StudyMenu extends AssistantMenuI {
  constructor() {
    super();
  }

  getList() {
    return [
      { title: "Explain Concept", mcp: "study", input: true, confirmation: false },
      { title: "Create Flashcards", mcp: "study", input: true, confirmation: true },
      { title: "Summarize Article", mcp: "study", input: true, confirmation: false },
      { title: "Practice Quiz", mcp: "study", input: true, confirmation: false },
      { title: "Research Topic", mcp: "study", input: true, confirmation: false },
      { title: "Code Tutorial", mcp: "study", input: true, confirmation: false },
    ];
  }
}

export class ActivitiesMenu extends AssistantMenuI {
  constructor() {
    super();
  }

  //this will do a summary in obsi
  getList() {
    return [
      { title: "Add task", input: true, confirmation: true },
      { title: "Complete task", input: true, confirmation: true },
      { title: "Remove task", input: true, confirmation: true },
    ];
  }
}
