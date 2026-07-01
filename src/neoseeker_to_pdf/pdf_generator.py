import os
from io import BytesIO
from typing import Any

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject
from playwright.sync_api import sync_playwright
from reportlab.pdfgen import canvas


PDF_DEST_KEY = "/Dest"
PDF_ACTION_KEY = "/A"
PDF_ACTION_TYPE_KEY = "/S"
PDF_ACTION_GOTO = "/GoTo"


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

                const resizedImages = Array.from(document.querySelectorAll("img[data-generated-resized='1']"));
                for (const image of resizedImages) {
                    const originalWidth = image.getAttribute("data-generated-original-width") || "";
                    const originalHeight = image.getAttribute("data-generated-original-height") || "";

                    if (originalWidth) {
                        image.style.width = originalWidth;
                    } else {
                        image.style.removeProperty("width");
                    }

                    if (originalHeight) {
                        image.style.height = originalHeight;
                    } else {
                        image.style.removeProperty("height");
                    }

                    image.style.removeProperty("max-width");
                    image.removeAttribute("data-generated-resized");
                    image.removeAttribute("data-generated-original-width");
                    image.removeAttribute("data-generated-original-height");
                }
            };

            const getRelevantImagesForBlock = (element) => {
                if (!element) {
                    return [];
                }

                const tag = element.tagName.toLowerCase();
                if (tag !== "p" && tag !== "center") {
                    return [];
                }

                const images = Array.from(element.querySelectorAll("img"));
                if (images.length === 0) {
                    return [];
                }

                // Ignore tiny inline/icon images to avoid over-grouping unrelated content.
                const significant = images.filter((img) => {
                    const rect = img.getBoundingClientRect();
                    return rect.width >= 120 && rect.height >= 120;
                });

                return significant;
            };

            const getHeadingImageContext = (heading) => {
                if (!heading || heading.tagName.toLowerCase() !== "h2") {
                    return null;
                }

                const hr = heading.nextElementSibling;
                if (!hr || hr.tagName.toLowerCase() !== "hr") {
                    return null;
                }

                const block = hr.nextElementSibling;
                if (!block) {
                    return null;
                }

                const blockTag = block.tagName.toLowerCase();
                if (blockTag === "p" || blockTag === "center") {
                    const images = getRelevantImagesForBlock(block);
                    if (images.length === 0) {
                        return null;
                    }
                    return { heading, hr, block, images };
                }

                if (blockTag === "div" && block.classList.contains("image-wrapper")) {
                    const images = Array.from(block.querySelectorAll("img"));
                    if (images.length === 0) {
                        return null;
                    }
                    return { heading, hr, block, images };
                }

                return null;
            };

            const findNearestPrecedingH1 = (heading) => {
                const result = document.evaluate(
                    "preceding::h1[1]",
                    heading,
                    null,
                    XPathResult.FIRST_ORDERED_NODE_TYPE,
                    null,
                );
                return result.singleNodeValue;
            };

            const canAttachH1ToHeadingBlock = (titleH1, heading) => {
                if (!titleH1 || !heading) {
                    return false;
                }

                const h1Top = getAbsoluteTop(titleH1);
                const h2Top = getAbsoluteTop(heading);
                if (h2Top <= h1Top || (h2Top - h1Top) > 260) {
                    return false;
                }

                const range = document.createRange();
                range.setStartAfter(titleH1);
                range.setEndBefore(heading);
                const fragment = range.cloneContents();

                if (fragment.querySelector("img, table, .alert, h2, h3, h4, h5, h6")) {
                    return false;
                }

                const betweenText = (fragment.textContent || "").replace(/\\s+/g, " ").trim();
                return betweenText.length <= 40;
            };

            const findAttachablePretitleBeforeH1 = (titleH1) => {
                if (!titleH1) {
                    return null;
                }

                const candidate = titleH1.previousElementSibling;
                if (!candidate) {
                    return null;
                }

                const tag = candidate.tagName.toLowerCase();
                if (tag !== "div" && tag !== "p") {
                    return null;
                }

                if (candidate.querySelector("img, table, .alert, h1, h2, h3, h4, h5, h6")) {
                    return null;
                }

                const strong = candidate.querySelector("strong");
                if (!strong) {
                    return null;
                }

                const candidateTop = getAbsoluteTop(candidate);
                const h1Top = getAbsoluteTop(titleH1);
                if (h1Top <= candidateTop || (h1Top - candidateTop) > 120) {
                    return null;
                }

                const text = (candidate.textContent || "").replace(/\\s+/g, " ").trim();
                if (!text || text.length > 120) {
                    return null;
                }

                return candidate;
            };

            const applyMinimalImageScaleToFitGroup = (item, remainingOnPage) => {
                if (!item.wrapper) {
                    return false;
                }

                // Avoid shrinking multi-image galleries; prefer a clean page break.
                if (!item.images || item.images.length !== 1) {
                    return false;
                }

                const groupHeight = item.wrapper.getBoundingClientRect().height;
                if (groupHeight <= 0 || groupHeight <= remainingOnPage) {
                    return false;
                }

                const imageRects = item.images.map((img) => ({
                    img,
                    rect: img.getBoundingClientRect(),
                }));
                const totalImageHeight = imageRects.reduce((sum, entry) => sum + entry.rect.height, 0);
                if (totalImageHeight <= 0) {
                    return false;
                }

                const nonImageHeight = Math.max(0, groupHeight - totalImageHeight);
                const availableForImages = remainingOnPage - nonImageHeight - 2;
                if (availableForImages <= 0) {
                    return false;
                }

                const scale = Math.min(1, availableForImages / totalImageHeight);
                const minAllowedScale = 0.90;
                if (scale < minAllowedScale) {
                    return false;
                }
                if (scale >= 0.995) {
                    return false;
                }

                for (const entry of imageRects) {
                    const img = entry.img;
                    if (!img.hasAttribute("data-generated-resized")) {
                        img.setAttribute("data-generated-original-width", img.style.width || "");
                        img.setAttribute("data-generated-original-height", img.style.height || "");
                    }

                    const newWidth = Math.max(1, entry.rect.width * scale);
                    const newHeight = Math.max(1, entry.rect.height * scale);
                    img.style.width = `${newWidth}px`;
                    img.style.height = `${newHeight}px`;
                    img.style.setProperty("max-width", "none", "important");
                    img.setAttribute("data-generated-resized", "1");
                }

                return true;
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

            for (const heading of Array.from(document.querySelectorAll("h2"))) {
                const context = getHeadingImageContext(heading);
                if (!context) {
                    continue;
                }

                const precedingH1 = findNearestPrecedingH1(heading);
                if (canAttachH1ToHeadingBlock(precedingH1, heading)) {
                    context.titleH1 = precedingH1;
                    context.pretitle = findAttachablePretitleBeforeH1(precedingH1);
                }

                headingImageBlocks.push(context);
            }

            for (const item of headingImageBlocks) {
                const wrapper = document.createElement("div");
                wrapper.className = "generated-title-image-group";
                wrapper.style.setProperty("break-inside", "avoid-page", "important");
                wrapper.style.setProperty("page-break-inside", "avoid", "important");

                const insertionAnchor = item.pretitle || item.titleH1 || item.heading;
                const parent = insertionAnchor.parentNode;
                if (!parent) {
                    continue;
                }

                parent.insertBefore(wrapper, insertionAnchor);
                if (item.pretitle) {
                    wrapper.appendChild(item.pretitle);
                }
                if (item.titleH1) {
                    wrapper.appendChild(item.titleH1);
                }
                wrapper.appendChild(item.heading);
                wrapper.appendChild(item.hr);
                wrapper.appendChild(item.block);
                item.wrapper = wrapper;
                item.breakElement = item.pretitle || item.titleH1 || item.heading;
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
                setBreakBeforePage(item.breakElement || item.heading, false);
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
                const breakElement = item.breakElement || item.heading;
                const headingTop = getAbsoluteTop(breakElement);
                const offsetInPage = getOffsetInPage(headingTop, pageHeightPx);
                const remainingOnPage = getSpaceToNextPage(offsetInPage, pageHeightPx);
                const groupHeight = item.wrapper ? item.wrapper.getBoundingClientRect().height : 0;

                if (groupHeight <= 0) {
                    continue;
                }

                if (groupHeight > remainingOnPage) {
                    applyMinimalImageScaleToFitGroup(item, remainingOnPage);
                    const resizedGroupHeight = item.wrapper ? item.wrapper.getBoundingClientRect().height : groupHeight;

                    if (resizedGroupHeight > remainingOnPage) {
                        setBreakBeforePage(breakElement, true);
                        if (!headingBreakSet.has(breakElement)) {
                            headingBreakSet.add(breakElement);
                            forcedHeadingBreaks += 1;
                        }
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
                const isAlertBlock = element.classList && element.classList.contains("alert");

                if (elementHeight <= 0) {
                    continue;
                }

                // Generic keep-together is too aggressive for long alerts.
                // Alert-specific rules are handled separately (e.g. title + image blocks).
                if (isAlertBlock) {
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


def _collect_chapter_metadata(page) -> list[dict[str, str]]:
    return page.evaluate(
        """
        () => {
            const chapters = Array.from(document.querySelectorAll("section.chapter"));
            const result = [];

            for (let index = 0; index < chapters.length; index += 1) {
                const section = chapters[index];
                const heading = section.querySelector("h1, h2, h3, h4, h5, h6");
                const title = (heading?.textContent || section.getAttribute("id") || `Capitulo ${index + 1}`).trim();
                const anchor = section.getAttribute("id") || `chapter-${String(index + 1).padStart(3, "0")}`;
                result.push({ anchor, title });
            }

            if (result.length === 0) {
                result.push({ anchor: "chapter-001", title: "Capitulo 1" });
            }

            return result;
        }
        """
    )


def _collect_chapter_page_starts_by_layout(
    page,
    margin_top_mm: float,
    margin_bottom_mm: float,
) -> list[dict[str, int | str]]:
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

            for (let index = 0; index < chapters.length; index += 1) {
                const section = chapters[index];
                const heading = section.querySelector("h1, h2, h3, h4, h5, h6");
                const title = (heading?.textContent || section.getAttribute("id") || `Capitulo ${index + 1}`).trim();
                const anchor = section.getAttribute("id") || `chapter-${String(index + 1).padStart(3, "0")}`;
                const top = section.getBoundingClientRect().top + window.scrollY;
                const pageNumber = Math.max(1, Math.floor(top / printableHeightPx) + 1);
                result.push({ anchor, title, page: pageNumber });
            }

            if (result.length === 0) {
                result.push({ anchor: "chapter-001", title: "Capitulo 1", page: 1 });
            }

            return result;
        }
        """,
        {
            "marginTopMm": margin_top_mm,
            "marginBottomMm": margin_bottom_mm,
        },
    )


def _build_page_ref_map(reader: PdfReader) -> dict[int, int]:
    mapping: dict[int, int] = {}
    for idx, pdf_page in enumerate(reader.pages, start=1):
        ref = getattr(pdf_page, "indirect_reference", None)
        if ref is not None and hasattr(ref, "idnum"):
            mapping[int(ref.idnum)] = idx
    return mapping


def _resolve_destination_page_number(
    reader: PdfReader,
    page_ref_to_number: dict[int, int],
    destination: Any,
) -> int | None:
    if destination is None:
        return None

    if isinstance(destination, str):
        try:
            named = reader.named_destinations.get(destination)
            if named is None:
                return None
            return reader.get_destination_page_number(named) + 1
        except Exception:
            return None

    if isinstance(destination, list) and destination:
        target = destination[0]
        if hasattr(target, "idnum"):
            return page_ref_to_number.get(int(target.idnum))
        if hasattr(target, "indirect_reference") and hasattr(target.indirect_reference, "idnum"):
            return page_ref_to_number.get(int(target.indirect_reference.idnum))

    return None


def _annotation_destination(annotation: Any) -> Any:
    destination = annotation.get(PDF_DEST_KEY)
    if destination is not None:
        return destination

    action = annotation.get(PDF_ACTION_KEY)
    if action and action.get(PDF_ACTION_TYPE_KEY) == PDF_ACTION_GOTO:
        return action.get("/D")

    return None


def _extract_toc_target_pages(pdf_bytes: bytes, expected_count: int) -> list[int]:
    reader = PdfReader(BytesIO(pdf_bytes))
    page_ref_to_number = _build_page_ref_map(reader)

    pages: list[int] = []
    for pdf_page in reader.pages:
        annotations = pdf_page.get("/Annots") or []
        for annot_ref in annotations:
            annotation = annot_ref.get_object()
            if annotation.get("/Subtype") != "/Link":
                continue

            destination = _annotation_destination(annotation)
            page_number = _resolve_destination_page_number(reader, page_ref_to_number, destination)
            if page_number is None:
                continue

            pages.append(page_number)
            if len(pages) >= expected_count:
                return pages

    return pages


def _build_chapter_starts_from_ordered_pages(
    chapter_metadata: list[dict[str, str]],
    ordered_pages: list[int],
) -> list[dict[str, int | str]]:
    if len(ordered_pages) < len(chapter_metadata):
        return []

    starts: list[dict[str, int | str]] = []
    for index, meta in enumerate(chapter_metadata):
        starts.append(
            {
                "anchor": meta["anchor"],
                "title": meta["title"],
                "page": int(ordered_pages[index]),
            }
        )
    return starts


def _apply_toc_page_numbers(page, chapter_starts: list[dict[str, int | str]]) -> int:
    return page.evaluate(
        """
        ({ chapterStarts }) => {
            const orderedPages = chapterStarts.map((item) => Number(item.page));

            let updated = 0;
            const items = Array.from(document.querySelectorAll("#table-of-contents .toc-item"));
            for (let idx = 0; idx < items.length; idx += 1) {
                if (idx >= orderedPages.length) {
                    continue;
                }

                const pageNumber = orderedPages[idx];
                const item = items[idx];
                const pageNode = item.querySelector(".toc-page");
                if (pageNode) {
                    pageNode.textContent = String(pageNumber).padStart(2, "0");
                }
                updated += 1;
            }

            return updated;
        }
        """,
        {"chapterStarts": chapter_starts},
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
    overlay.drawCentredString(width_pt / 2.0, footer_y, f"{page_number:02d}")
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

    # Keep full PDF structure (named destinations/links/outlines) so hyperlinks continue working.
    if hasattr(writer, "clone_document_from_reader"):
        writer.clone_document_from_reader(reader)
    else:
        for page in reader.pages:
            writer.add_page(page)

    for index, source_page in enumerate(writer.pages, start=1):
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

    _normalize_internal_links(writer, reader)

    with open(output_pdf, "wb") as output_stream:
        writer.write(output_stream)


def _resolve_named_destination_page(reader: PdfReader, destination: str) -> int | None:
    try:
        named = reader.named_destinations.get(destination)
        if named is None:
            return None
        return reader.get_destination_page_number(named) + 1
    except Exception:
        return None


def _resolve_array_destination_page(page_ref_to_number: dict[int, int], destination: list[Any]) -> int | None:
    if not destination:
        return None

    target = destination[0]
    if hasattr(target, "idnum"):
        return page_ref_to_number.get(int(target.idnum))
    if hasattr(target, "indirect_reference") and hasattr(target.indirect_reference, "idnum"):
        return page_ref_to_number.get(int(target.indirect_reference.idnum))
    return None


def _resolve_link_target_page_number(
    reader: PdfReader,
    page_ref_to_number: dict[int, int],
    annotation: Any,
) -> int | None:
    destination = annotation.get(PDF_DEST_KEY)
    if destination is None:
        action = annotation.get(PDF_ACTION_KEY)
        if action and action.get(PDF_ACTION_TYPE_KEY) == PDF_ACTION_GOTO:
            destination = action.get("/D")

    if destination is None:
        return None

    if isinstance(destination, str):
        return _resolve_named_destination_page(reader, destination)

    if isinstance(destination, list):
        return _resolve_array_destination_page(page_ref_to_number, destination)

    return None


def _normalize_page_links(
    writer: PdfWriter,
    reader: PdfReader,
    page_ref_to_number: dict[int, int],
    page: Any,
) -> None:
    annotations = page.get("/Annots") or []
    for annotation_ref in annotations:
        annotation = annotation_ref.get_object()
        if annotation.get("/Subtype") != "/Link":
            continue

        target_page_number = _resolve_link_target_page_number(reader, page_ref_to_number, annotation)
        if not target_page_number:
            continue

        target_page = writer.pages[target_page_number - 1]
        target_ref = getattr(target_page, "indirect_reference", None)
        if target_ref is None:
            continue

        annotation[NameObject(PDF_ACTION_KEY)] = DictionaryObject(
            {
                NameObject(PDF_ACTION_TYPE_KEY): NameObject(PDF_ACTION_GOTO),
                NameObject("/D"): ArrayObject([target_ref, NameObject("/Fit")]),
            }
        )
        if PDF_DEST_KEY in annotation:
            del annotation[PDF_DEST_KEY]


def _normalize_internal_links(writer: PdfWriter, reader: PdfReader) -> None:
    page_ref_to_number = _build_page_ref_map(reader)
    for page in writer.pages:
        _normalize_page_links(writer, reader, page_ref_to_number, page)


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
        chapter_metadata = _collect_chapter_metadata(page)
        first_pass_pdf_bytes = page.pdf(
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

        ordered_pages = _extract_toc_target_pages(first_pass_pdf_bytes, len(chapter_metadata))
        chapter_starts = _build_chapter_starts_from_ordered_pages(chapter_metadata, ordered_pages)
        if not chapter_starts:
            chapter_starts = _collect_chapter_page_starts_by_layout(page, margin_top_mm, margin_bottom_mm)

        toc_updated = _apply_toc_page_numbers(page, chapter_starts)
        print("Cabecera/Pie: capitulos dinamicos por pagina en margen")
        print(f"Capitulos detectados: {len(chapter_starts)}")
        print(f"Indice actualizado con paginas: {toc_updated}")
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
