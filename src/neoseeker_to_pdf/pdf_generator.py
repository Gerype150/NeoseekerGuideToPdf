import os
from io import BytesIO

from pypdf import PdfReader, PdfWriter
from playwright.sync_api import sync_playwright
from reportlab.pdfgen import canvas


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

            const unwrapGeneratedGroups = () => {
                const groups = Array.from(
                    document.querySelectorAll(
                        "div.generated-title-image-group, div.generated-alert-head-group, div.generated-title-table-group"
                    )
                );
                for (const group of groups) {
                    const parent = group.parentNode;
                    if (!parent) {
                        continue;
                    }

                    while (group.firstChild) {
                        parent.insertBefore(group.firstChild, group);
                    }
                    parent.removeChild(group);
                }
            };

            const getImageOnlyBlockImage = (element) => {
                if (!element) {
                    return null;
                }

                const tag = element.tagName.toLowerCase();
                if (tag !== "p" && tag !== "center") {
                    return null;
                }

                const text = element.textContent || "";
                if (text.trim()) {
                    return null;
                }

                const images = Array.from(element.querySelectorAll("img"));
                if (images.length !== 1) {
                    return null;
                }

                return images[0];
            };

            const getHeadingContextForSiblingBlock = (block) => {
                const maybeHr = block.previousElementSibling;
                if (!maybeHr || maybeHr.tagName.toLowerCase() !== "hr") {
                    return null;
                }

                const maybeH2 = maybeHr.previousElementSibling;
                if (!maybeH2 || maybeH2.tagName.toLowerCase() !== "h2") {
                    return null;
                }

                return { heading: maybeH2, hr: maybeHr };
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

            unwrapGeneratedGroups();

            const pageHeightPx = probe.getBoundingClientRect().height || 1122;
            probe.remove();

            const elements = Array.from(document.querySelectorAll(targetSelectors.join(",")));
            const pageTitles = Array.from(document.querySelectorAll("div#page-title"));
            const tableContainers = new Set();
            const headingImageBlocks = [];
            const alertHeadGroups = [];
            const headingTableGroups = [];

            for (const element of elements) {
                if (element.tagName.toLowerCase() !== "table") {
                    continue;
                }

                const container = element.closest("div.section.section-info");
                if (container) {
                    tableContainers.add(container);
                }
            }

            for (const block of Array.from(document.querySelectorAll("p, center"))) {
                const image = getImageOnlyBlockImage(block);
                if (!image) {
                    continue;
                }

                const headingContext = getHeadingContextForSiblingBlock(block);
                if (!headingContext) {
                    continue;
                }

                headingImageBlocks.push({ block, image, heading: headingContext.heading, hr: headingContext.hr });
            }

            for (const item of headingImageBlocks) {
                const wrapper = document.createElement("div");
                wrapper.className = "generated-title-image-group";
                wrapper.style.setProperty("break-inside", "avoid-page", "important");
                wrapper.style.setProperty("page-break-inside", "avoid", "important");

                const parent = item.heading.parentNode;
                if (!parent) {
                    continue;
                }

                parent.insertBefore(wrapper, item.heading);
                wrapper.appendChild(item.heading);
                wrapper.appendChild(item.hr);
                wrapper.appendChild(item.block);
            }

            for (const alert of Array.from(document.querySelectorAll("div.alert"))) {
                const title = alert.querySelector(":scope > h3");
                if (!title) {
                    continue;
                }

                let imageBlock = null;
                let cursor = title.nextElementSibling;
                while (cursor) {
                    const tag = cursor.tagName.toLowerCase();
                    if (tag === "p" || tag === "center" || tag === "div") {
                        const img = cursor.querySelector("img");
                        if (img) {
                            imageBlock = cursor;
                            break;
                        }
                    }

                    if (tag === "p" && (cursor.textContent || "").trim()) {
                        break;
                    }

                    cursor = cursor.nextElementSibling;
                }

                if (!imageBlock) {
                    continue;
                }

                const wrapper = document.createElement("div");
                wrapper.className = "generated-alert-head-group";
                wrapper.style.setProperty("break-inside", "avoid-page", "important");
                wrapper.style.setProperty("page-break-inside", "avoid", "important");

                alert.insertBefore(wrapper, title);
                wrapper.appendChild(title);
                wrapper.appendChild(imageBlock);
                alertHeadGroups.push({ alert, wrapper });
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
            for (const item of headingImageBlocks) {
                setBreakBeforePage(item.heading, false);
            }
            for (const item of alertHeadGroups) {
                setBreakBeforePage(item.alert, false);
            }

            let keepTogetherApplied = 0;
            let forcedPageTitleBreaks = 0;
            let forcedHeadingBreaks = 0;
            let forcedAlertHeadBreaks = 0;
            const appliedTargets = new Set();
            const headingBreakSet = new Set();

            for (const title of pageTitles) {
                const absoluteTop = getAbsoluteTop(title);
                const offsetInPage = getOffsetInPage(absoluteTop, pageHeightPx);
                const shouldBreak = offsetInPage > 0;

                setBreakBeforePage(title, shouldBreak);
                if (shouldBreak) {
                    forcedPageTitleBreaks += 1;
                }
            }

            for (const item of headingImageBlocks) {
                const imageRect = item.image.getBoundingClientRect();
                const imageHeight = imageRect.height;
                if (imageHeight <= 0 || imageHeight >= pageHeightPx * 0.98) {
                    continue;
                }

                const blockTop = getAbsoluteTop(item.block);
                const offsetInPage = getOffsetInPage(blockTop, pageHeightPx);
                const remainingOnPage = getSpaceToNextPage(offsetInPage, pageHeightPx);

                if (imageHeight > remainingOnPage) {
                    setBreakBeforePage(item.heading, true);
                    if (!headingBreakSet.has(item.heading)) {
                        headingBreakSet.add(item.heading);
                        forcedHeadingBreaks += 1;
                    }
                }
            }

            for (const item of alertHeadGroups) {
                const groupRect = item.wrapper.getBoundingClientRect();
                const groupHeight = groupRect.height;
                if (groupHeight <= 0 || groupHeight >= pageHeightPx * 0.98) {
                    continue;
                }

                const alertTop = getAbsoluteTop(item.alert);
                const offsetInPage = getOffsetInPage(alertTop, pageHeightPx);
                const remainingOnPage = getSpaceToNextPage(offsetInPage, pageHeightPx);

                if (groupHeight > remainingOnPage) {
                    setBreakBeforePage(item.alert, true);
                    forcedAlertHeadBreaks += 1;
                }
            }

            for (const table of Array.from(document.querySelectorAll("table"))) {
                const optionalParagraph = table.previousElementSibling;
                let hr = null;
                let heading = null;

                if (optionalParagraph && optionalParagraph.tagName.toLowerCase() === "p") {
                    hr = optionalParagraph.previousElementSibling;
                } else {
                    hr = table.previousElementSibling;
                }

                if (!hr || hr.tagName.toLowerCase() !== "hr") {
                    continue;
                }

                heading = hr.previousElementSibling;
                if (!heading || heading.tagName.toLowerCase() !== "h2") {
                    continue;
                }

                if (heading.closest("div.generated-title-table-group")) {
                    continue;
                }

                const group = document.createElement("div");
                group.className = "generated-title-table-group";
                group.style.setProperty("break-inside", "avoid-page", "important");
                group.style.setProperty("page-break-inside", "avoid", "important");

                const parent = heading.parentNode;
                if (!parent) {
                    continue;
                }

                parent.insertBefore(group, heading);
                group.appendChild(heading);
                group.appendChild(hr);
                if (optionalParagraph && optionalParagraph.tagName.toLowerCase() === "p") {
                    group.appendChild(optionalParagraph);
                }
                group.appendChild(table);

                headingTableGroups.push({ heading, group });
            }

            let forcedTitleTableBreaks = 0;
            for (const item of headingTableGroups) {
                const groupRect = item.group.getBoundingClientRect();
                const groupHeight = groupRect.height;
                if (groupHeight <= 0 || groupHeight >= pageHeightPx * 0.98) {
                    continue;
                }

                const headingTop = getAbsoluteTop(item.heading);
                const offsetInPage = getOffsetInPage(headingTop, pageHeightPx);
                const remainingOnPage = getSpaceToNextPage(offsetInPage, pageHeightPx);

                if (groupHeight > remainingOnPage) {
                    setBreakBeforePage(item.heading, true);
                    forcedTitleTableBreaks += 1;
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
                forcedHeadingBreaks,
                forcedAlertHeadBreaks,
                forcedTitleTableBreaks,
            };
        }
        """
    )


def _collect_chapter_page_starts(page, margin_top_mm: float, margin_bottom_mm: float) -> list[dict[str, int | str]]:
    return page.evaluate(
        """
        ({ marginTopMm, marginBottomMm }) => {
            const mmProbe = document.createElement("div");
            mmProbe.style.position = "absolute";
            mmProbe.style.visibility = "hidden";
            mmProbe.style.pointerEvents = "none";
            mmProbe.style.height = "1mm";
            mmProbe.style.left = "0";
            mmProbe.style.top = "0";
            document.body.appendChild(mmProbe);
            const pxPerMm = mmProbe.getBoundingClientRect().height || 3.78;
            mmProbe.remove();

            const pageProbe = document.createElement("div");
            pageProbe.style.position = "absolute";
            pageProbe.style.visibility = "hidden";
            pageProbe.style.pointerEvents = "none";
            pageProbe.style.height = "297mm";
            pageProbe.style.left = "0";
            pageProbe.style.top = "0";
            document.body.appendChild(pageProbe);
            const pageHeightPx = pageProbe.getBoundingClientRect().height || 1122;
            pageProbe.remove();

            const printableHeightPx = Math.max(
                1,
                pageHeightPx - (marginTopMm * pxPerMm) - (marginBottomMm * pxPerMm),
            );

            const chapters = Array.from(document.querySelectorAll("section.chapter"));
            const result = [];
            let lastPage = -1;

            for (let index = 0; index < chapters.length; index += 1) {
                const section = chapters[index];
                const heading = section.querySelector("h1, h2, h3, h4, h5, h6");
                const title = (heading?.textContent || section.getAttribute("id") || `Capitulo ${index + 1}`).trim();
                const top = section.getBoundingClientRect().top + window.scrollY;
                const pageNumber = Math.max(1, Math.floor(top / printableHeightPx) + 1);

                if (pageNumber <= lastPage) {
                    continue;
                }

                result.push({ title, page: pageNumber });
                lastPage = pageNumber;
            }

            if (result.length === 0) {
                result.push({ title: "Neoseeker Walkthrough", page: 1 });
            }

            return result;
        }
        """,
        {
            "marginTopMm": margin_top_mm,
            "marginBottomMm": margin_bottom_mm,
        },
    )


def _mm_to_points(mm: float) -> float:
    return mm * 72.0 / 25.4


def _resolve_chapter_for_page(chapter_starts: list[dict[str, int | str]], page_number: int) -> str:
    active_title = str(chapter_starts[0]["title"])
    for item in chapter_starts:
        if page_number >= int(item["page"]):
            active_title = str(item["title"])
        else:
            break
    return active_title


def _build_overlay_page(
    width_pt: float,
    height_pt: float,
    chapter_title: str,
    page_number: int,
    margin_top_mm: float,
    margin_bottom_mm: float,
) -> bytes:
    packet = BytesIO()
    overlay = canvas.Canvas(packet, pagesize=(width_pt, height_pt))
    overlay.setFont("Times-Roman", 10)
    overlay.setFillColorRGB(0.23, 0.23, 0.23)

    top_margin_pt = _mm_to_points(margin_top_mm)
    bottom_margin_pt = _mm_to_points(margin_bottom_mm)

    header_y = max(height_pt - top_margin_pt + 8, height_pt - (top_margin_pt / 2.0))
    footer_y = max(6, bottom_margin_pt / 2.0)

    overlay.drawCentredString(width_pt / 2.0, header_y, chapter_title)
    overlay.drawCentredString(width_pt / 2.0, footer_y, str(page_number))
    overlay.save()

    packet.seek(0)
    return packet.read()


def _write_annotated_pdf(
    base_pdf_bytes: bytes,
    output_pdf: str,
    chapter_starts: list[dict[str, int | str]],
    margin_top_mm: float,
    margin_bottom_mm: float,
) -> None:
    reader = PdfReader(BytesIO(base_pdf_bytes))
    writer = PdfWriter()

    for index, source_page in enumerate(reader.pages, start=1):
        page_width = float(source_page.mediabox.width)
        page_height = float(source_page.mediabox.height)
        chapter_title = _resolve_chapter_for_page(chapter_starts, index)

        overlay_bytes = _build_overlay_page(
            page_width,
            page_height,
            chapter_title,
            index,
            margin_top_mm,
            margin_bottom_mm,
        )
        overlay_reader = PdfReader(BytesIO(overlay_bytes))
        overlay_page = overlay_reader.pages[0]

        source_page.merge_page(overlay_page)
        writer.add_page(source_page)

    with open(output_pdf, "wb") as output_stream:
        writer.write(output_stream)


def generate_pdf(
    html_file: str,
    output_pdf: str,
    margin_top_mm: float = 20.0,
    margin_bottom_mm: float = 16.0,
    margin_left_mm: float = 14.0,
    margin_right_mm: float = 14.0,
) -> None:
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
            f"h2Breaks={policy_stats['forcedHeadingBreaks']},",
            f"alertHeadBreaks={policy_stats['forcedAlertHeadBreaks']},",
            f"titleTableBreaks={policy_stats['forcedTitleTableBreaks']}",
        )
        chapter_starts = _collect_chapter_page_starts(page, margin_top_mm, margin_bottom_mm)
        print("Cabecera/Pie: capitulos dinamicos por pagina en margen")
        print(f"Capitulos detectados: {len(chapter_starts)}")
        page.wait_for_timeout(1000)
        try:
            base_pdf_bytes = page.pdf(
                format="A4",
                margin={
                    "top": f"{margin_top_mm}mm",
                    "bottom": f"{margin_bottom_mm}mm",
                    "left": f"{margin_left_mm}mm",
                    "right": f"{margin_right_mm}mm",
                },
                print_background=True,
                prefer_css_page_size=True,
            )
            _write_annotated_pdf(
                base_pdf_bytes=base_pdf_bytes,
                output_pdf=output_pdf,
                chapter_starts=chapter_starts,
                margin_top_mm=margin_top_mm,
                margin_bottom_mm=margin_bottom_mm,
            )
        except PermissionError as exc:
            raise PermissionError(
                f"No se pudo escribir '{output_pdf}'. Cierra el PDF si esta abierto e intenta de nuevo."
            ) from exc

        browser.close()

    print("PDF creado")
