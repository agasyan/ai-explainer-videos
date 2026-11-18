# Research: visual patterns for narrated explainers

Gathered 2026-11-18 by researcher agents, each source opened on the web. Every claim needs two independent sources; a claim with one is marked "one source". [visual-patterns.md](../visual-patterns.md) turns these into scene rules.

## Learning from narrated animation (L)

| id | claim | source 1 | source 2 | status |
|---|---|---|---|---|
| L1 | Coherence: cut extraneous material. Median d = 0.86 | https://my.chartered.college/impact_article/how-multimedia-can-improve-learning-and-instruction/ | https://www.unh.edu/teaching-learning-resource-hub/sites/default/files/media/2023-06/itow-research-based-principles-for-designing-multimedia-instruction-mayer.pdf | confirmed |
| L2 | Signaling: cue the essential material. d = 0.41 (2014 table), 0.70 (2021 table) | same as L1 | same as L1 | confirmed; size differs by edition |
| L3 | Redundancy: narration plus identical on-screen text does not help. d = 0.86 (2014), 0.10 (2021) | same as L1 | same as L1 | confirmed on direction; size disputed |
| L4 | Spatial contiguity: words next to the part they name. d = 1.10 (2014), 0.82 (2021) | same as L1 | same as L1 | confirmed |
| L5 | Temporal contiguity: words while the matching picture shows. d = 1.22 (2014), 1.31 (2021) | same as L1 | same as L1 | confirmed |
| L6 | Segmenting: break the lesson into parts. d = 0.77 (2014), 0.67 (2021); measured for learner-paced lessons | same as L1 | same as L1 | confirmed; partly applies to video |
| L7 | Pre-training: name the key parts before the process. d = 0.75 (2014), 0.78 (2021) | same as L1 | same as L1 | confirmed |
| L8 | Personalization: a conversational style. d = 0.79 (2014), 1.00 (2021) | same as L1 | same as L1 | confirmed |
| L9 | Captions: 2 lines at most | https://partnerhelp.netflixstudios.com/hc/en-us/articles/217350977-English-Timed-Text-Style-Guide | https://design.shelter.org.uk/digital-framework/video-captioning | confirmed |
| L10 | Caption line length: Netflix 42 characters, Shelter 38 | same as L9 | same as L9 | confirmed; limits differ |
| L11 | Reading speed: Netflix up to 20 characters a second for adults | https://partnerhelp.netflixstudios.com/hc/en-us/articles/217350977-English-Timed-Text-Style-Guide | https://clevercast.com/bbc-subtitling-guidelines (a vendor summary of the BBC) | confirmed on Netflix |
| L12 | Caption duration: Netflix 5/6 s minimum, 7 s maximum | https://partnerhelp.netflixstudios.com/hc/en-us/articles/215758617-Timed-Text-Style-Guide-Subtitle-Timing-Guidelines | https://clevercast.com/bbc-subtitling-guidelines | confirmed on Netflix |
| L13 | In 6.9M edX sessions, median engagement is 6 min at most, whatever the length; 0 to 3 min videos are mostly watched past three quarters | https://www.cs.rochester.edu/hci/pubs/pdfs/edX-MOOC-video-production-and-engagement_LAS-2014.pdf | (none opened) | one source; lecture videos |
| L14 | Speaking rates ran 48 to 254 words a minute (mean 156); faster speech held viewers longer | same as L13 | (none opened) | one source |

## Data stories and motion (P)

| id | claim | source 1 | source 2 | status |
|---|---|---|---|---|
| P1 | Narrative visualization genres sit on a scale from author-driven to reader-driven; film and video is author-driven | https://idl.uw.edu/papers/narrative | https://data.europa.eu/apps/data-visualisation-guide/narrative-visualisation-genres-introduction | confirmed |
| P2 | Martini glass: an author-driven opening, then a reader sandbox; a slideshow fixes the order | https://data.europa.eu/apps/data-visualisation-guide/martini-glass-story-structure | https://mser521.github.io/fall2025/resources/narrative-visualization | confirmed |
| P3 | Minto pyramid: lead with the answer, then grouped support | https://thinkinsights.net/index.php/strategy/pyramid-principle | https://modelthinkers.com/mental-model/225 | confirmed |
| P4 | The Big Idea: one complete sentence with a point of view and the stakes | https://www.storytellingwithdata.com/blog/2014/02/whats-big-idea | https://www.storytellingwithdata.com/blog/2014/02/the-3-minute-story | one source (one publisher) |
| P5 | For one or two numbers, show big numbers, not a chart | https://www.storytellingwithdata.com/blog/2021/5/20/storytelling-with-simple-text | https://www.concordusa.com/blog/data-driven-storytelling-tip-10-use-callout-numbers | confirmed |
| P6 | Pick the form by the relationship: magnitude, ranking, change over time, part to whole, flow | https://github.com/Financial-Times/chart-doctor/blob/main/visual-vocabulary/README.md | https://www.data-to-viz.com/ | confirmed |
| P7 | Before and after per item: slope chart or dumbbell | https://github.com/Financial-Times/chart-doctor/blob/main/visual-vocabulary/README.md | https://www.data-to-viz.com/graph/lollipop.html | confirmed |
| P8 | A process is a flowchart; a diamond is a decision with 2 paths | https://datavizcatalogue.com/methods/flow_chart.html | https://en.wikipedia.org/wiki/Flowchart | confirmed |
| P9 | A table when exact values matter; color the outliers | https://cambridge.org/core/journals/journal-of-benefit-cost-analysis/article/ten-guidelines-for-better-tables/74C6FD9FEB12038A52A95B9FBCA05A12 | https://themockup.blog/posts/2020-09-04-10-table-rules-in-r | confirmed |
| P10 | Animated transitions between chart states improve perception; moving the same mark keeps object constancy | https://idl.uw.edu/papers/animated-transitions | https://bost.ocks.org/mike/constancy/ | confirmed |
| P11 | Staggered starts gave little or no tracking benefit | https://api.openalex.org/works/doi:10.1109/TVCG.2014.2346424 | (none) | one source |
| P12 | Animated trends are engaging but cause errors; small multiples are more accurate | https://www.microsoft.com/en-us/research/publication/effectiveness-of-animation-in-trend-visualization/ | https://arxiv.org/abs/1907.03919 | confirmed (shared co-author) |
| P13 | Build a chart with the narration: axes, then data in story order, then the highlight | https://www.storytellingwithdata.com/blog/2014/06/leveraging-animation-what-you-present | https://www.brightcarbon.com/blog/animating-powerpoint-graphs/ | confirmed |
| P14 | Words with their pictures at the same time beat words then pictures | https://www.cambridge.org/core/books/multimedia-learning/temporal-contiguity-principle/2B975B185589B381663F342F0363515F | (none) | one source; see L5 |
| P15 | Signaling (color, arrows, spotlights, zoom) improves retention (g+ 0.53) and transfer (g+ 0.33) | https://qic-wd.org/node/672 | https://inspire.acu.edu.au/articles/signalling | confirmed (summaries) |
| P16 | Ken Burns effect: a slow zoom or pan on a still, toward the subject | https://en.wikipedia.org/wiki/Ken_Burns_effect | https://support.apple.com/en-ie/guide/imovie/movc6e02f503/mac | confirmed |
| P17 | Screencast tools zoom a rectangle onto one screen region | https://www.techsmith.com/learn/tutorials/academy/edit-your-videos-to-focus-students-attention/ | https://screen.studio/ | confirmed |
| P18 | A spotlight keeps one region bright and dims the rest | https://www.techsmith.com/learn/tutorials/snagit/spotlight/ | https://atomisystems.com/?p=61115 | confirmed |

## Limits

- Mayer's effect sizes differ between the 2014 and 2021 tables; quote ranges, not one number.
- The BBC caption figures come from a vendor summary; the BBC pages did not load.
- The full papers of Segel and Heer, and of Heer and Robertson, were checked from abstracts and landing pages only.
- L13 and L14 study lecture videos, not short explainers.
