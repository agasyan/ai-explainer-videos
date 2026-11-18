# Research: the New video dialog

Gathered 2026-11-18 by a researcher agent, each source opened on the web. It shaped the dashboard's New video dialog ([dashboard.md](../dashboard.md)).

| id | claim | source 1 | source 2 | status |
|---|---|---|---|---|
| U1 | A modal fits short, blocking, user-started input; complex work belongs on a full page | https://www.nngroup.com/articles/modal-nonmodal-dialog/ | https://carbondesignsystem.com/components/modal/usage/ | confirmed |
| U3 | Cloudscape: a modal for 1 primary field; 2 to 15 fields on a single page | https://cloudscape.design/patterns/resource-management/create/ | https://www.nngroup.com/articles/modal-nonmodal-dialog/ | confirmed; argues for a large dialog or a page |
| U4 | Modal accessibility: focus moves in, Tab wraps, Escape closes, focus returns, a visible title labels it | https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/ | https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/dialog | confirmed |
| U5 | Forms in modals: focus the first input, validate inline, keep the modal open on error | https://carbondesignsystem.com/components/modal/usage/ | https://www.nngroup.com/articles/modal-nonmodal-dialog/ | confirmed |
| U6 | One screen for a few short, related groups; a wizard costs clicks and hides earlier answers | https://www.nngroup.com/articles/wizards/ | https://cloudscape.design/patterns/resource-management/create/ | confirmed |
| U8 | Progressive disclosure: frequent options first, the rest in one labelled second level | https://www.nngroup.com/articles/progressive-disclosure/ | https://cloudscape.design/patterns/resource-management/create/ | confirmed |
| U9 | Smart defaults let people skip fields | https://cloudscape.design/patterns/resource-management/create/ | https://www.nngroup.com/articles/wizards/ | confirmed |
| U10 | A segmented control picks one of a small set; short labels of one kind | https://carbondesignsystem.com/components/content-switcher/usage/ | https://primer.style/components/segmented-control/ | confirmed |
| U12 | Add-another rows: a unique label per item, "Add another" names the thing, remove names the item | https://designsystem.gov.scot/patterns/add-more-fields | https://design-system.dwp.gov.uk/patterns/add-another-thing/how-it-works | confirmed |
| U13 | Move focus to the new row on add, and announce adds and removes | https://designsystem.gov.scot/patterns/add-more-fields | https://www.w3.org/WAI/ARIA/apg/patterns/button/ | one source for the details |
| U14 | Card pickers are a radio group with a visible group label | https://www.w3.org/WAI/ARIA/apg/patterns/radio/ | https://carbondesignsystem.com/components/tile/usage/ | confirmed |
| U15 | Sound only from a click: no autoplay | https://www.w3.org/WAI/WCAG22/Understanding/audio-control.html | https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Autoplay | confirmed |
| U16 | A play button is a native button named by its text | https://www.w3.org/WAI/ARIA/apg/patterns/button/ | https://www.w3.org/WAI/WCAG22/Understanding/audio-control.html | one source for the toggle detail |

## How the dialog follows it

- A large native `<dialog>` with `showModal()`: focus trap, Escape, an inert page behind, a visible title (U1, U3, U4).
- One screen, 3 labelled groups (Sources; What you want; Look and sound), not a wizard (U6).
- Smart defaults: "Let Claude pick" for structure and look, a default voice, 1-3 min, 16:9; name, web research, and 3D under Advanced (U8, U9).
- Length and aspect as segmented radio groups (U10); structure and look as radio cards (U14).
- Source rows: "Source 2: kind", "Add another source", "Remove source 2"; focus moves to a new row, and adds and removes are announced (U12, U13).
- Voices: a native Play button per voice, nothing plays on its own (U15, U16).
- Errors stay inline, and the dialog stays open (U5).
