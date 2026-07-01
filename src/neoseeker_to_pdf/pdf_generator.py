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

            const alignSectionHeadingWithContainerBreak = (container) => {
                const maybeHr = container.previousElementSibling;
                if (!maybeHr || maybeHr.tagName.toLowerCase() !== "hr") {
                    return;
                }

                const maybeH2 = maybeHr.previousElementSibling;
                if (!maybeH2 || maybeH2.tagName.toLowerCase() !== "h2") {
                    return;
                }

                // Move section title separators together with the section-info block.
                setBreakBeforePage(maybeH2, true);
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
            const tableContainers = new Set();

            for (const element of elements) {
                if (element.tagName.toLowerCase() !== "table") {
                    continue;
                }

                const container = element.closest("div.section.section-info");
                if (container) {
                    tableContainers.add(container);
                }
            }

            // Reset print-related inline styles so each run starts clean.
            for (const element of elements) {
                setBreakInside(element, "auto");
            }
            for (const container of tableContainers) {
                setBreakInside(container, "auto");
            }
            for (const title of pageTitles) {
                setBreakBeforePage(title, false);
            }
            for (const container of tableContainers) {
                const maybeHr = container.previousElementSibling;
                if (maybeHr && maybeHr.tagName.toLowerCase() === "hr") {
                    const maybeH2 = maybeHr.previousElementSibling;
                    if (maybeH2 && maybeH2.tagName.toLowerCase() === "h2") {
                        setBreakBeforePage(maybeH2, false);
                    }
                }
            }

            let keepTogetherApplied = 0;
            let forcedPageTitleBreaks = 0;
            const appliedTargets = new Set();

            for (const title of pageTitles) {
                const absoluteTop = getAbsoluteTop(title);
                const offsetInPage = getOffsetInPage(absoluteTop, pageHeightPx);
                const shouldBreak = offsetInPage > 0;

                setBreakBeforePage(title, shouldBreak);
                if (shouldBreak) {
                    forcedPageTitleBreaks += 1;
                }
            }

            for (const element of elements) {
                const rect = element.getBoundingClientRect();
                const elementHeight = rect.height;
                const absoluteTop = getAbsoluteTop(element);
                const offsetInPage = getOffsetInPage(absoluteTop, pageHeightPx);
                const remainingOnPage = getSpaceToNextPage(offsetInPage, pageHeightPx);

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
                        let target = element;
                        if (element.tagName.toLowerCase() === "table") {
                            const container = element.closest("div.section.section-info");
                            if (container) {
                                target = container;
                            }
                        }

                        setBreakInside(target, "avoid-page");
                        if (target !== element) {
                            alignSectionHeadingWithContainerBreak(target);
                        }
                        if (!appliedTargets.has(target)) {
                            appliedTargets.add(target);
                            keepTogetherApplied += 1;
                        }
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
