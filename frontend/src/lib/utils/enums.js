export const NoteRequestType = {
    FOLLOWING: 1,
    SPECIFIC_USER: 2,
    GLOBAL: 3,
    SEARCH_TEXT: 4,
    SEARCH_HASHTAG: 5,
    SEARCH_USER: 6,
    TEST_ERROR: 99
};

export const NoteType = {
    STANDARD: 1,
    REPLY: 2,
    QUOTE: 3,
    REPOST: 4
};

export const NoteRequestTypeNames = {
    [NoteRequestType.FOLLOWING]: 'Following',
    [NoteRequestType.SPECIFIC_USER]: 'Specific User',
    [NoteRequestType.GLOBAL]: 'Global',
    [NoteRequestType.HASHTAG]: 'Hashtag',
    [NoteRequestType.SEARCH]: 'Search'
};

export const SearchTypeLabels = {
    [NoteRequestType.SEARCH_TEXT]: 'Text Search',
    [NoteRequestType.SEARCH_HASHTAG]: 'Hashtag/Topic Search',
    [NoteRequestType.SEARCH_USER]: 'Name | NPUB Search'
};