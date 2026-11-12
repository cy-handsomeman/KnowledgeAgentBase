export const state = {
  user: null,
  groups: [],
  knowledgeBases: [],
  selectedGroupId: null,
  selectedKbId: null,
  chatSessions: [],
  chatMessages: [],
  currentSessionId: null,
  chatKbId: null,
  chatSending: false,
};

export async function refreshWorkspace() {
  const [groups, knowledgeBases] = await Promise.all([
    apiFetch("/api/groups"),
    apiFetch("/api/knowledge-bases"),
  ]);
  state.groups = groups;
  state.knowledgeBases = knowledgeBases;
}

export function canEditKnowledgeBase(knowledgeBase) {
  if (!knowledgeBase) {
    return false;
  }
  if (knowledgeBase.scope_type === "personal") {
    return true;
  }
  const group = state.groups.find((item) => item.id === knowledgeBase.group_id);
  return Boolean(group) && ["editor", "admin"].includes(group.role);
}
