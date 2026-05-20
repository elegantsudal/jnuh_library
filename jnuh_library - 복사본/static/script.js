const isAuthenticated = document.body.dataset.authenticated === "true";
let selectedTheme = "";

document.addEventListener("DOMContentLoaded", () => {
    if (isAuthenticated) {
        initializeSearchUi();
        initializeProfilePanel();
        initializeRecordForm();
        initializeLogout();
        return;
    }

    initializeAuthTabs();
    initializeLoginForm();
    initializeSignupForm();
});

function initializeAuthTabs() {
    const tabs = document.querySelectorAll(".auth-tab");
    const forms = document.querySelectorAll(".auth-form");

    tabs.forEach((tab) => {
        tab.addEventListener("click", () => {
            tabs.forEach((button) => button.classList.remove("active"));
            forms.forEach((form) => form.classList.remove("active"));

            tab.classList.add("active");
            const target = document.getElementById(tab.dataset.target);
            if (target) {
                target.classList.add("active");
            }
        });
    });
}

function initializeLoginForm() {
    const form = document.getElementById("loginForm");
    if (!form) {
        return;
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const payload = Object.fromEntries(new FormData(form).entries());
        const message = document.getElementById("loginMessage");

        setFormMessage(message, "로그인 중입니다...", "success");

        try {
            const response = await fetch("/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await response.json();

            if (!response.ok) {
                setFormMessage(message, data.message || "로그인에 실패했습니다.", "error");
                return;
            }

            setFormMessage(message, data.message || "로그인되었습니다.", "success");
            window.location.reload();
        } catch (error) {
            setFormMessage(message, "서버와 통신하지 못했습니다.", "error");
        }
    });
}

function initializeSignupForm() {
    const form = document.getElementById("signupForm");
    if (!form) {
        return;
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const payload = Object.fromEntries(new FormData(form).entries());
        const message = document.getElementById("signupMessage");

        setFormMessage(message, "회원가입을 진행하고 있습니다...", "success");

        try {
            const response = await fetch("/signup", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await response.json();

            if (!response.ok) {
                setFormMessage(message, data.message || "회원가입에 실패했습니다.", "error");
                return;
            }

            setFormMessage(message, data.message || "회원가입이 완료되었습니다.", "success");
            window.location.reload();
        } catch (error) {
            setFormMessage(message, "서버와 통신하지 못했습니다.", "error");
        }
    });
}

function initializeLogout() {
    const logoutButton = document.getElementById("logoutButton");
    if (!logoutButton) {
        return;
    }

    logoutButton.addEventListener("click", async () => {
        try {
            await fetch("/logout", { method: "POST" });
        } finally {
            window.location.reload();
        }
    });
}

function initializeSearchUi() {
    const searchButton = document.getElementById("searchButton");
    const searchInput = document.getElementById("searchInput");
    const themeButtons = document.querySelectorAll(".theme-item");

    if (searchButton) {
        searchButton.addEventListener("click", () => searchBooks());
    }

    if (searchInput) {
        searchInput.addEventListener("keydown", (event) => {
            if (event.key === "Enter") {
                searchBooks();
            }
        });

        searchInput.addEventListener("input", () => {
            if (selectedTheme && searchInput.value.trim() !== selectedTheme) {
                setSelectedTheme("");
                setActiveThemeButton(null);
            }
        });
    }

    themeButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const theme = button.dataset.theme;
            setSelectedTheme(theme);
            setActiveThemeButton(button);
            if (searchInput) {
                searchInput.value = theme;
            }
            searchBooks(theme);
        });
    });
}

function initializeProfilePanel() {
    const profileButton = document.getElementById("profileButton");
    const profilePanel = document.getElementById("profilePanel");

    if (!profileButton || !profilePanel) {
        return;
    }

    profileButton.addEventListener("click", (event) => {
        event.stopPropagation();
        const isOpen = !profilePanel.classList.contains("hidden");
        setProfilePanelOpen(!isOpen);
    });

    profilePanel.addEventListener("click", (event) => {
        event.stopPropagation();
    });

    document.addEventListener("click", () => {
        setProfilePanelOpen(false);
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            setProfilePanelOpen(false);
            closeRecordModal();
        }
    });
}

function initializeRecordForm() {
    const form = document.getElementById("recordForm");
    const closeButton = document.getElementById("closeRecordModal");
    const modal = document.getElementById("recordModal");

    if (!form) {
        return;
    }

    if (closeButton) {
        closeButton.addEventListener("click", closeRecordModal);
    }

    if (modal) {
        modal.addEventListener("click", (event) => {
            if (event.target.dataset.closeRecordModal === "true") {
                closeRecordModal();
            }
        });
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        const payload = Object.fromEntries(new FormData(form).entries());
        const message = document.getElementById("recordMessage");

        if (!payload.theme_name) {
            setFormMessage(message, "기록할 테마를 선택해주세요.", "error");
            return;
        }

        setFormMessage(message, "기록을 저장하고 있습니다...", "success");

        try {
            const response = await fetch("/record-book", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await response.json();

            if (!response.ok) {
                setFormMessage(message, data.message || "도서 기록 저장에 실패했습니다.", "error");
                return;
            }

            setFormMessage(message, data.message || "도서 기록이 저장되었습니다.", "success");
            setSelectedTheme(data.theme_name || payload.theme_name);
            setTimeout(() => {
                closeRecordModal();
                window.location.reload();
            }, 700);
        } catch (error) {
            setFormMessage(message, "서버와 통신하지 못했습니다.", "error");
        }
    });
}

async function searchBooks(themeQuery = null) {
    const searchInput = document.getElementById("searchInput");
    const results = document.getElementById("results");
    const query = themeQuery || (searchInput ? searchInput.value.trim() : "");
    const queryType = themeQuery ? "Keyword" : "Title";

    if (!query) {
        results.innerHTML = "<p class='message'>검색어를 입력해주세요.</p>";
        return;
    }

    results.innerHTML = "<p class='message'>도서를 찾고 있습니다...</p>";

    try {
        const response = await fetch(
            `/search?q=${encodeURIComponent(query)}&queryType=${encodeURIComponent(queryType)}`
        );
        const data = await response.json();

        if (!response.ok) {
            results.innerHTML = `<p class="message">${data.error || "검색 중 오류가 발생했습니다."}</p>`;
            if (response.status === 401) {
                setTimeout(() => window.location.reload(), 800);
            }
            return;
        }

        if (!data.books || data.books.length === 0) {
            results.innerHTML = "<p class='message'>검색 결과가 없습니다.</p>";
            return;
        }

        const themeForRecord =
            themeQuery || (selectedTheme && query === selectedTheme) ? (themeQuery || selectedTheme) : "";

        results.innerHTML = data.books
            .map(
                (book) => `
                    <article class="book">
                        ${
                            book.cover
                                ? `<img src="${book.cover}" alt="${escapeHtml(book.title)}">`
                                : `<div class="book-placeholder">알라딘</div>`
                        }
                        <p class="book-type">${escapeHtml(book.type || "도서")}</p>
                        <h3>${escapeHtml(book.title)}</h3>
                        <p>${escapeHtml(book.author || "저자 정보 없음")}</p>
                        <p>${formatPublisherLine(book)}</p>
                        <p>${escapeHtml(book.location || "알라딘 도서 검색")}</p>
                        ${
                            book.isbn
                                ? `<p>ISBN ${escapeHtml(book.isbn)}</p>`
                                : ""
                        }
                        ${
                            book.link
                                ? `<a href="${book.link}" target="_blank" rel="noopener noreferrer">알라딘 상세보기</a>`
                                : ""
                        }
                        <button
                            type="button"
                            class="record-book-button"
                            data-book-title="${escapeHtml(book.title)}"
                            data-theme-name="${escapeHtml(themeForRecord)}"
                        >
                            기록 남기기
                        </button>
                    </article>
                `
            )
            .join("");

        initializeRecordButtons();
    } catch (error) {
        results.innerHTML = "<p class='message'>서버와 통신하지 못했습니다.</p>";
    }
}

function setFormMessage(element, message, type) {
    if (!element) {
        return;
    }

    element.textContent = message;
    element.classList.remove("error", "success");

    if (type) {
        element.classList.add(type);
    }
}

function setSelectedTheme(themeName) {
    selectedTheme = themeName || "";
    const themeInput = document.getElementById("recordTheme");
    if (themeInput) {
        themeInput.value = selectedTheme;
    }
}

function setActiveThemeButton(activeButton) {
    document.querySelectorAll(".theme-item").forEach((button) => {
        button.classList.toggle("active", button === activeButton);
    });
}

function formatPublisherLine(book) {
    const parts = [book.publisher, book.publish_year].filter(Boolean);
    return escapeHtml(parts.length > 0 ? parts.join(" · ") : "발행 정보 없음");
}

function initializeRecordButtons() {
    document.querySelectorAll(".record-book-button").forEach((button) => {
        button.addEventListener("click", () => {
            openRecordModal({
                themeName: button.dataset.themeName || "",
                bookTitle: button.dataset.bookTitle || "",
            });
        });
    });
}

function openRecordModal({ themeName, bookTitle }) {
    const modal = document.getElementById("recordModal");
    const recordTheme = document.getElementById("recordTheme");
    const bookTitleInput = document.getElementById("bookTitle");
    const reflection = document.getElementById("reflection");
    const message = document.getElementById("recordMessage");

    if (!modal || !recordTheme || !bookTitleInput || !reflection) {
        return;
    }

    recordTheme.value = themeName || "";
    bookTitleInput.value = bookTitle || "";
    reflection.value = "";
    setFormMessage(message, "", "");
    modal.classList.remove("hidden");
    modal.setAttribute("aria-hidden", "false");
    document.body.classList.add("modal-open");
    setTimeout(() => reflection.focus(), 10);
}

function closeRecordModal() {
    const modal = document.getElementById("recordModal");
    const form = document.getElementById("recordForm");
    const message = document.getElementById("recordMessage");

    if (!modal) {
        return;
    }

    if (form) {
        form.reset();
    }
    setSelectedTheme(selectedTheme);
    setFormMessage(message, "", "");
    modal.classList.add("hidden");
    modal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("modal-open");
}

function setProfilePanelOpen(isOpen) {
    const profileButton = document.getElementById("profileButton");
    const profilePanel = document.getElementById("profilePanel");

    if (!profileButton || !profilePanel) {
        return;
    }

    profilePanel.classList.toggle("hidden", !isOpen);
    profilePanel.setAttribute("aria-hidden", String(!isOpen));
    profileButton.setAttribute("aria-expanded", String(isOpen));
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}
