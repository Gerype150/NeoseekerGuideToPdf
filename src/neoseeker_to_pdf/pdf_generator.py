import os

from playwright.sync_api import sync_playwright


def _wait_for_images(page) -> None:
    page.evaluate(
        """
        () => {
            for (const image of Array.from(document.images)) {
                image.loading = "eager";
                image.decoding = "sync";
            }
        }
        """
    )

    page.evaluate(
        """
        async () => {
            const waitImage = (img) => new Promise((resolve) => {
                if (img.complete && img.naturalWidth > 0) {
                    resolve();
                    return;
                }

                const done = () => resolve();
                img.addEventListener("load", done, { once: true });
                img.addEventListener("error", done, { once: true });

                const src = img.getAttribute("src");
                if (src) {
                    img.src = src;
                }
            });

            const images = Array.from(document.images);

            // Trigger lazy-loaded images by traversing the whole document.
            const maxScroll = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
            for (let y = 0; y <= maxScroll; y += 800) {
                window.scrollTo(0, y);
                await new Promise((resolve) => setTimeout(resolve, 50));
            }
            window.scrollTo(0, 0);

            await Promise.all(images.map(waitImage));
        }
        """
    )


def _apply_print_break_policy(page) -> dict[str, int]:
    return page.evaluate(
        """
        () => {
            const targetSelectors = [
                "table",
                ".alert.alert-info",
                ".alert.alert-primary",
                ".alert.alert-success",
                ".alert.alert-error",
                ".alert.alert-danger",
                ".alert.alert-secondary",
            ];
            const maxBlankRatioToKeep = 0.15;

            const getAbsoluteTop = (element) => element.getBoundingClientRect().top + window.scrollY;

            const getOffsetInPage = (absoluteTop, pageHeight) => {
                return ((absoluteTop % pageHeight) + pageHeight) % pageHeight;
            };

            const getSpaceToNextPage = (offsetInPage, pageHeight) => {
                if (offsetInPage === 0) {
                    return 0;
                }
                return pageHeight - offsetInPage;
            };

            const setBreakInside = (element, mode) => {
                element.style.setProperty("break-inside", mode, "important");
                element.style.setProperty("page-break-inside", mode, "important");
            };

            const setBreakBeforePage = (element, enabled) => {
                const value = enabled ? "page" : "auto";
                const legacyValue = enabled ? "always" : "auto";
                element.style.setProperty("break-before", value, "important");
                element.style.setProperty("page-break-before", legacyValue, "important");
            };

            const probe = document.createElement("div");
            probe.style.position = "absolute";
            probe.style.visibility = "hidden";
            probe.style.pointerEvents = "none";
            probe.style.height = "297mm";
            probe.style.left = "0";
            probe.style.top = "0";
            document.body.appendChild(probe);

            const pageHeightPx = probe.getBoundingClientRect().height || 1122;
            probe.remove();

            const elements = Array.from(document.querySelectorAll(targetSelectors.join(",")));
            const pageTitles = Array.from(document.querySelectorAll("div#page-title"));

            // Reset print-related inline styles so each run starts clean.
            for (const element of elements) {
                setBreakInside(element, "auto");
            }
            for (const title of pageTitles) {
                setBreakBeforePage(title, false);
            }

            const candidateSelector = [
                "div#page-title",
                ...targetSelectors,
            ].join(",");
            const orderedNodes = Array.from(document.querySelectorAll(candidateSelector));

            const events = orderedNodes.flatMap((element) => {
                if (element.matches("div#page-title")) {
                    return [{ type: "pageTitle", element }];
                }

                if (element.matches(targetSelectors.join(","))) {
                    return [{ type: "keepCandidate", element }];
                }

                return [];
            });

            let keepTogetherApplied = 0;
            let forcedPageTitleBreaks = 0;
            for (const event of events) {
                const element = event.element;
                const rect = element.getBoundingClientRect();
                const elementHeight = rect.height;
                const absoluteTop = getAbsoluteTop(element);
                const offsetInPage = getOffsetInPage(absoluteTop, pageHeightPx);
                const remainingOnPage = getSpaceToNextPage(offsetInPage, pageHeightPx);

                if (event.type === "pageTitle") {
                    const shouldBreak = offsetInPage > 0;
                    setBreakBeforePage(element, shouldBreak);
                    if (shouldBreak) {
                        forcedPageTitleBreaks += 1;
                    }
                    continue;
                }

                if (event.type !== "keepCandidate") {
                    continue;
                }

                if (elementHeight <= 0) {
                    continue;
                }

                // Elements that already exceed a page must be allowed to split.
                if (elementHeight >= pageHeightPx * 0.98) {
                    continue;
                }

                if (elementHeight > remainingOnPage) {
                    const blankRatio = remainingOnPage / pageHeightPx;
                    const shouldKeepTogether = blankRatio <= maxBlankRatioToKeep;

                    if (shouldKeepTogether) {
                        setBreakInside(element, "avoid-page");
                        keepTogetherApplied += 1;
                    }
                }
            }

            return {
                candidates: elements.length,
                keepTogetherApplied,
                forcedPageTitleBreaks,
                forcedHeadingBreaks: 0,
            };
        }
        """
    )


def generate_pdf(html_file: str, output_pdf: str) -> None:
    print("Generando PDF...")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()

        page.goto(
            "file://" + os.path.abspath(html_file),
            wait_until="domcontentloaded",
            timeout=120000,
        )

        page.wait_for_load_state("networkidle", timeout=120000)
        _wait_for_images(page)
        page.emulate_media(media="print")
        policy_stats = _apply_print_break_policy(page)
        print(
            "Politica de salto:",
            f"candidatos={policy_stats['candidates']},",
            f"keepTogether={policy_stats['keepTogetherApplied']},",
            f"pageTitleBreaks={policy_stats['forcedPageTitleBreaks']},",
            f"h2Breaks={policy_stats['forcedHeadingBreaks']}",
        )
        page.wait_for_timeout(1000)
        try:
            page.pdf(
                path=output_pdf,
                format="A4",
                print_background=True,
                prefer_css_page_size=True,
            )
        except PermissionError as exc:
            raise PermissionError(
                f"No se pudo escribir '{output_pdf}'. Cierra el PDF si esta abierto e intenta de nuevo."
            ) from exc

        browser.close()

    print("PDF creado")
