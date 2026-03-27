/**
 * CineSense catalog frontend with movie details and recommendations.
 */

const API_BASE_URL = 'http://localhost:8000';
const TMDB_IMAGE_BASE = 'https://image.tmdb.org/t/p/w500';
const USER_PROFILE_KEY = 'cinesense_user_profile_v1';
const SEARCH_HISTORY_KEY = 'cinesense_search_history_v1';

const elements = {
    resultsHeader: document.getElementById('resultsHeader'),
    resultsGrid: document.getElementById('resultsGrid'),
    loading: document.getElementById('loading'),
    noResults: document.getElementById('noResults'),
    error: document.getElementById('error'),
    errorMessage: document.getElementById('errorMessage'),
    movieDetailContainer: document.getElementById('movieDetailContainer'),
    recommendationQuery: document.getElementById('recommendationQuery'),
    recommendationSearchBtn: document.getElementById('recommendationSearchBtn'),
    recommendationResetBtn: document.getElementById('recommendationResetBtn'),
    refreshRecommendationsBtn: document.getElementById('refreshRecommendationsBtn'),
    debugToggle: document.getElementById('debugToggle'),
    rerankToggle: document.getElementById('rerankToggle'),
    profileForm: document.getElementById('profileForm'),
    prefKeywords: document.getElementById('prefKeywords'),
    prefMinYear: document.getElementById('prefMinYear'),
    prefAbsaRefine: document.getElementById('prefAbsaRefine'),
    clearProfileBtn: document.getElementById('clearProfileBtn'),
    profileStatus: document.getElementById('profileStatus'),
};

const state = {
    currentPage: 1,
    pageSize: 24,
    totalMovies: 0,
    totalPages: 0,
    mode: 'catalog',
};

async function getMovies(page = 1, pageSize = 24) {
    const response = await fetch(`${API_BASE_URL}/movies?page=${page}&page_size=${pageSize}`);
    if (!response.ok) throw new Error('Không thể tải danh sách phim');
    return response.json();
}

async function getMovieDetails(movieId) {
    const response = await fetch(`${API_BASE_URL}/movies/${movieId}`);
    if (!response.ok) throw new Error('Không thể tải chi tiết phim');
    return response.json();
}

async function getSimilarMovies(movieId, limit = 8) {
    const response = await fetch(`${API_BASE_URL}/movies/${movieId}/similar?limit=${limit}`);
    if (!response.ok) throw new Error('Không thể tải phim tương tự');
    return response.json();
}

async function getTrendingRecommendations(limit = 24) {
    const response = await fetch(`${API_BASE_URL}/recommendations/trending?limit=${limit}`);
    if (!response.ok) throw new Error('Không thể tải gợi ý phim');
    return response.json();
}

function buildRecommendationPayload(query, limit = 24) {
    const history = loadSearchHistory();
    return {
        query,
        limit,
        query_type: 'auto',
        absa_refine: true,
        explain: true,
        debug: elements.debugToggle ? elements.debugToggle.checked : false,
        user_history: history.length ? history : undefined,
        rerank: elements.rerankToggle ? elements.rerankToggle.checked : false,
    };
}

function normalizeRecommendationResult(movie) {
    const normalized = normalizeMovieData(movie);
    const sb = movie.score_breakdown || null;
    if (!sb) return normalized;
    normalized.score_breakdown = {
        title: Number(sb.title ?? 0),
        genre: Number(sb.genre ?? 0),
        semantic: Number(sb.semantic ?? 0),
        bm25: Number(sb.bm25 ?? 0),
        user_match: Number(sb.user_match ?? 0),
        absa_bonus: Number(sb.absa_bonus ?? 0),
        final: Number(sb.final ?? normalized.score ?? 0),
    };
    return normalized;
}

async function searchRecommendations(payload) {
    const response = await fetch(`${API_BASE_URL}/recommendations/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error('Không thể tìm gợi ý');
    return response.json();
}

async function getAbsaAnalysis(movieId) {
    const response = await fetch(`${API_BASE_URL}/absa/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ movie_id: movieId }),
    });
    if (response.status === 503) return null;
    if (!response.ok) throw new Error('Không thể phân tích ABSA');
    return response.json();
}

function showLoading() {
    if (elements.loading) elements.loading.classList.remove('hidden');
    if (elements.error) elements.error.classList.add('hidden');
    if (elements.noResults) elements.noResults.classList.add('hidden');
    if (elements.resultsHeader) elements.resultsHeader.classList.add('hidden');
}

function hideLoading() {
    if (elements.loading) elements.loading.classList.add('hidden');
}

function showError(message) {
    hideLoading();
    if (elements.error) elements.error.classList.remove('hidden');
    if (elements.errorMessage) elements.errorMessage.textContent = message;
}

function showNoResults() {
    hideLoading();
    if (elements.noResults) elements.noResults.classList.remove('hidden');
}

function loadUserProfile() {
    try {
        const raw = window.localStorage.getItem(USER_PROFILE_KEY);
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== 'object') return null;
        return parsed;
    } catch (_e) {
        return null;
    }
}

function saveUserProfile(profile) {
    window.localStorage.setItem(USER_PROFILE_KEY, JSON.stringify(profile));
}

function clearUserProfile() {
    window.localStorage.removeItem(USER_PROFILE_KEY);
}

function loadSearchHistory() {
    try {
        const raw = window.localStorage.getItem(SEARCH_HISTORY_KEY);
        if (!raw) return [];
        const parsed = JSON.parse(raw);
        if (!Array.isArray(parsed)) return [];
        return parsed.filter((x) => typeof x === 'string' && x.trim()).slice(-30);
    } catch (_e) {
        return [];
    }
}

function saveSearchHistory(items) {
    try {
        window.localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(items.slice(-30)));
    } catch (_e) {
        // ignore
    }
}

function pushSearchHistory(query) {
    const q = (query || '').trim();
    if (!q) return;
    const items = loadSearchHistory();
    const next = items.filter((x) => x.toLowerCase() !== q.toLowerCase());
    next.push(q);
    saveSearchHistory(next);
}

function applyProfileDefaultsOnCatalog() {
    const profile = loadUserProfile();
    if (!profile) return;
    if (elements.recommendationQuery && !elements.recommendationQuery.value && profile.keywords) {
        elements.recommendationQuery.value = profile.keywords;
    }
}

function initProfilePage() {
    if (!elements.profileForm) return;
    const profile = loadUserProfile() || {};
    const genreSet = new Set(profile.genres || []);
    document.querySelectorAll('input[name="prefGenres"]').forEach((el) => {
        el.checked = genreSet.has(el.value);
    });
    if (elements.prefKeywords) elements.prefKeywords.value = profile.keywords || '';
    if (elements.prefMinYear) elements.prefMinYear.value = profile.min_year || '';
    if (elements.prefAbsaRefine) elements.prefAbsaRefine.checked = profile.absa_refine !== false;

    elements.profileForm.addEventListener('submit', (event) => {
        event.preventDefault();
        const genres = Array.from(document.querySelectorAll('input[name="prefGenres"]:checked')).map((el) => el.value);
        const payload = {
            genres,
            keywords: elements.prefKeywords?.value?.trim() || '',
            min_year: elements.prefMinYear?.value ? Number.parseInt(elements.prefMinYear.value, 10) : null,
            absa_refine: elements.prefAbsaRefine ? elements.prefAbsaRefine.checked : true,
            updated_at: new Date().toISOString(),
        };
        saveUserProfile(payload);
        if (elements.profileStatus) elements.profileStatus.textContent = 'Đã lưu hồ sơ thành công.';
    });

    if (elements.clearProfileBtn) {
        elements.clearProfileBtn.addEventListener('click', () => {
            clearUserProfile();
            document.querySelectorAll('input[name="prefGenres"]').forEach((el) => {
                el.checked = false;
            });
            if (elements.prefKeywords) elements.prefKeywords.value = '';
            if (elements.prefMinYear) elements.prefMinYear.value = '';
            if (elements.prefAbsaRefine) elements.prefAbsaRefine.checked = true;
            if (elements.profileStatus) elements.profileStatus.textContent = 'Đã dọn hồ sơ.';
        });
    }
}

function getPosterUrl(posterPath) {
    return posterPath ? `${TMDB_IMAGE_BASE}${posterPath}` : null;
}

function normalizeMovieData(movie) {
    const normalizedGenres = (movie.genres || []).map((genre) =>
        typeof genre === 'string' ? { name: genre } : genre
    );
    return {
        id: movie.id || movie.movie_id,
        title: movie.title,
        overview: movie.overview,
        poster_path: movie.poster_path,
        review_count: movie.review_count || 0,
        average_rating: movie.average_rating ?? null,
        release_date: movie.release_date || null,
        genres: normalizedGenres,
        score: movie.score ?? null,
        score_breakdown: movie.score_breakdown ?? null,
    };
}

function renderScoreBreakdown(movie) {
    const sb = movie.score_breakdown;
    if (!sb) return '';
    return `
        <div class="score-breakdown">
            <span class="score-chip">T:${Number(sb.title ?? 0).toFixed(2)}</span>
            <span class="score-chip">G:${Number(sb.genre ?? 0).toFixed(2)}</span>
            <span class="score-chip">S:${Number(sb.semantic ?? 0).toFixed(2)}</span>
            <span class="score-chip">BM25:${Number(sb.bm25 ?? 0).toFixed(2)}</span>
            <span class="score-chip">U:${Number(sb.user_match ?? 0).toFixed(2)}</span>
            <span class="score-chip">ABSA:+${Number(sb.absa_bonus ?? 0).toFixed(2)}</span>
        </div>
    `;
}

function createMovieCard(inputMovie) {
    const movie = normalizeMovieData(inputMovie);
    const card = document.createElement('article');
    card.className = 'card-movie';

    const posterUrl = getPosterUrl(movie.poster_path);
    const genres = (movie.genres || []).slice(0, 2);
    const year = movie.release_date ? new Date(movie.release_date).getFullYear() : 'N/A';

    card.innerHTML = `
        <div class="card-poster">
            ${posterUrl ? `<img src="${posterUrl}" alt="${movie.title}" loading="lazy">` : '<div style="height:100%;background:#eee;"></div>'}
            ${movie.average_rating ? `<div class="card-star-rating">★ ${movie.average_rating.toFixed(1)}</div>` : ''}
        </div>
        <div class="card-info">
            <h3 class="card-title">${movie.title}</h3>
            <div class="card-meta">
                <span>${year}</span>
                ${genres.map((genre) => `<span class="card-genre">${genre.name}</span>`).join('')}
            </div>
            ${movie.review_count ? `<div class="card-review-count">${movie.review_count} đánh giá</div>` : ''}
            ${movie.score !== null && movie.score !== undefined ? `<div class="card-review-count">Độ phù hợp: ${movie.score.toFixed(2)}</div>` : ''}
            ${renderScoreBreakdown(movie)}
            ${movie.overview ? `<p class="card-overview">${movie.overview.slice(0, 120)}${movie.overview.length > 120 ? '...' : ''}</p>` : ''}
        </div>
    `;

    card.addEventListener('click', () => {
        window.location.href = `movie.html?id=${movie.id}`;
    });

    return card;
}

function renderMovieCards(movies) {
    if (!elements.resultsGrid) return;
    elements.resultsGrid.innerHTML = '';
    movies.forEach((movie) => {
        elements.resultsGrid.appendChild(createMovieCard(movie));
    });
}

function renderHeader(title, subtitle) {
    if (!elements.resultsHeader) return;
    elements.resultsHeader.classList.remove('hidden');
    elements.resultsHeader.innerHTML = `
        <h2 class="section-title">${title}</h2>
        <p style="color: #9ca3af; margin-top: 4px; font-size: 0.95rem;">${subtitle}</p>
        <div id="debugPanel" class="hidden" style="margin-top: 12px;"></div>
    `;
}

function renderDebugPanel(debug, payload) {
    const panel = document.getElementById('debugPanel');
    if (!panel) return;
    const enabled = elements.debugToggle ? elements.debugToggle.checked : false;
    if (!enabled || !debug) {
        panel.classList.add('hidden');
        panel.innerHTML = '';
        return;
    }
    panel.classList.remove('hidden');
    const pretty = (obj) => {
        try {
            return JSON.stringify(obj, null, 2);
        } catch (_e) {
            return String(obj);
        }
    };
    const explainer = (() => {
        const n = Array.isArray(debug.tokens) ? debug.tokens.length : 0;
        const w = debug.weights || {};
        const intents = Array.isArray(debug.absa_intents) ? debug.absa_intents.length : 0;
        const hist = debug.personalization ? Number(debug.personalization.history_count ?? 0) : 0;
        const ce = debug.rerank?.enabled ? 'bật' : 'tắt';
        return `Query ${n} token → auto-weight (T=${Number(w.title ?? 0).toFixed(2)}, G=${Number(w.genre ?? 0).toFixed(2)}, S=${Number(w.semantic ?? 0).toFixed(2)}). ABSA intents=${intents}. History=${hist}. Cross-Encoder=${ce}.`;
    })();

    panel.innerHTML = `
        <div class="advanced-panel" style="padding: 14px;">
            <div style="color:#e5e7eb; font-size:0.95rem; margin-bottom:10px;">${explainer}</div>
            <div style="display:flex; gap:10px; flex-wrap:wrap; align-items:center;">
                <span class="score-chip">mode: ${debug.query_type_requested || 'auto'}</span>
                <span class="score-chip">w_title: ${Number(debug.weights?.title ?? 0).toFixed(2)}</span>
                <span class="score-chip">w_genre: ${Number(debug.weights?.genre ?? 0).toFixed(2)}</span>
                <span class="score-chip">w_sem: ${Number(debug.weights?.semantic ?? 0).toFixed(2)}</span>
                <span class="score-chip">semantic_ready: ${debug.semantic_ready ? 'yes' : 'no'}</span>
                <span class="score-chip">absa_profile_ready: ${debug.absa_profile_ready ? 'yes' : 'no'}</span>
                ${debug.personalization ? `<span class="score-chip">history: ${Number(debug.personalization.history_count ?? 0)}</span>` : ''}
                ${debug.personalization ? `<span class="score-chip">user_vec: ${debug.personalization.user_vec_ready ? 'yes' : 'no'}</span>` : ''}
                ${debug.rerank ? `<span class="score-chip">rerank: ${debug.rerank.enabled ? 'on' : 'off'}</span>` : ''}
            </div>
            <div style="margin-top: 10px; display:grid; gap:10px;">
                <div>
                    <div style="color:#9ca3af; font-size:0.9rem; margin-bottom:6px;">Query normalize & tokens</div>
                    <pre style="white-space:pre-wrap; background:#0b1220; color:#d1d5db; padding:12px; border-radius:12px; overflow:auto;">${pretty({ query_raw: debug.query_raw, query_normalized: debug.query_normalized, tokens: debug.tokens, absa_intents: debug.absa_intents })}</pre>
                </div>
                <div>
                    <div style="color:#9ca3af; font-size:0.9rem; margin-bottom:6px;">Request payload gửi lên API</div>
                    <pre style="white-space:pre-wrap; background:#0b1220; color:#d1d5db; padding:12px; border-radius:12px; overflow:auto;">${pretty(payload)}</pre>
                </div>
            </div>
        </div>
    `;
}

function renderMovieList(data) {
    hideLoading();
    if (!data.movies || data.movies.length === 0) {
        removePagination();
        showNoResults();
        return;
    }

    state.totalMovies = data.total;
    state.totalPages = Math.ceil(data.total / data.page_size);
    state.currentPage = data.page;

    renderHeader('Danh sách phim', `${data.total} phim trong cơ sở dữ liệu`);
    renderMovieCards(data.movies);
    renderPagination();
}

async function loadMovies() {
    state.mode = 'catalog';
    showLoading();
    try {
        const data = await getMovies(state.currentPage, state.pageSize);
        renderMovieList(data);
    } catch (error) {
        console.error('Load movies failed:', error);
        showError(error.message || 'Không thể tải danh sách phim');
    }
}

async function loadTrendingRecommendations() {
    state.mode = 'recommendation';
    showLoading();
    removePagination();
    try {
        const data = await getTrendingRecommendations(24);
        hideLoading();
        if (!data.results.length) return showNoResults();
        renderHeader('Gợi ý nổi bật', `Mô hình: ${data.model}`);
        renderMovieCards(data.results);
    } catch (error) {
        // Fallback gracefully to catalog when artifacts are missing.
        console.warn('Trending recommendations unavailable:', error.message);
        loadMovies();
    }
}

async function runRecommendationSearch() {
    if (!elements.recommendationQuery) return;
    const query = elements.recommendationQuery.value.trim();
    if (!query) {
        loadMovies();
        return;
    }

    state.mode = 'recommendation';
    showLoading();
    removePagination();
    try {
        pushSearchHistory(query);
        const payload = buildRecommendationPayload(query, 24);
        const data = await searchRecommendations(payload);
        hideLoading();
        if (!data.results.length) return showNoResults();
        const modeLabel = payload.query_type || 'auto';
        renderHeader('Kết quả tìm gợi ý', `"${query}" • mô hình: ${data.model} • chế độ: ${modeLabel}`);
        renderDebugPanel(data.debug || null, payload);
        renderMovieCards((data.results || []).map(normalizeRecommendationResult));
    } catch (error) {
        console.error('Recommendation search failed:', error);
        showError(error.message || 'Không thể tìm gợi ý');
    }
}

function buildProfileQuery(profile) {
    const parts = [];
    if (profile?.keywords) parts.push(profile.keywords);
    if (Array.isArray(profile?.genres) && profile.genres.length) parts.push(profile.genres.slice(0, 3).join(' '));
    return parts.join(' ').trim();
}

function buildPayloadFromProfile(profile, limit = 24) {
    const query = buildProfileQuery(profile);
    const payload = buildRecommendationPayload(query || 'movie', limit);
    payload.absa_refine = profile?.absa_refine !== false;
    if (profile?.min_year) payload.filters = { min_year: profile.min_year };
    if (Array.isArray(profile?.genres) && profile.genres.length) {
        payload.filters = { ...(payload.filters || {}), genres: profile.genres };
    }
    return payload;
}

async function loadRecommendationsForYou() {
    const profile = loadUserProfile();
    if (!profile) {
        showNoResults();
        return;
    }
    const payload = buildPayloadFromProfile(profile, 24);
    state.mode = 'recommendation';
    showLoading();
    removePagination();
    try {
        const data = await searchRecommendations(payload);
        hideLoading();
        const results = (data.results || []).map(normalizeRecommendationResult);
        if (!results.length) return showNoResults();
        renderHeader('Gợi ý cho bạn', `Dựa trên hồ sơ • mô hình: ${data.model}`);
        renderDebugPanel(data.debug || null, payload);
        renderMovieCards(results);
    } catch (error) {
        showError(error.message || 'Không thể tải gợi ý');
    }
}

function renderPagination() {
    removePagination();
    if (!elements.resultsGrid || state.totalPages <= 1 || state.mode !== 'catalog') return;

    const container = document.createElement('div');
    container.id = 'paginationControls';
    container.className = 'pagination';
    const pages = generatePageNumbers(state.currentPage, state.totalPages);

    container.innerHTML = `
        <button class="page-btn ${state.currentPage <= 1 ? 'disabled' : ''}" id="prevPage" ${state.currentPage <= 1 ? 'disabled' : ''}>← Prev</button>
        <div class="page-numbers">
            ${pages.map((page) => page === '...' ? '<span class="page-ellipsis">...</span>' : `<button class="page-num ${page === state.currentPage ? 'active' : ''}" data-page="${page}">${page}</button>`).join('')}
        </div>
        <button class="page-btn ${state.currentPage >= state.totalPages ? 'disabled' : ''}" id="nextPage" ${state.currentPage >= state.totalPages ? 'disabled' : ''}>Next →</button>
    `;

    elements.resultsGrid.parentNode.insertBefore(container, elements.resultsGrid.nextSibling);
    document.getElementById('prevPage').addEventListener('click', () => {
        if (state.currentPage <= 1) return;
        state.currentPage -= 1;
        loadMovies();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
    document.getElementById('nextPage').addEventListener('click', () => {
        if (state.currentPage >= state.totalPages) return;
        state.currentPage += 1;
        loadMovies();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
    container.querySelectorAll('.page-num').forEach((button) => {
        button.addEventListener('click', () => {
            const page = Number.parseInt(button.dataset.page, 10);
            if (page === state.currentPage) return;
            state.currentPage = page;
            loadMovies();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    });
}

function generatePageNumbers(current, total) {
    if (total <= 7) return Array.from({ length: total }, (_, index) => index + 1);
    const pages = [1];
    if (current > 3) pages.push('...');
    const start = Math.max(2, current - 1);
    const end = Math.min(total - 1, current + 1);
    for (let page = start; page <= end; page += 1) pages.push(page);
    if (current < total - 2) pages.push('...');
    pages.push(total);
    return pages;
}

function removePagination() {
    const existing = document.getElementById('paginationControls');
    if (existing) existing.remove();
}

function createReviewCard(review) {
    const authorName = review.author_name || review.source || 'Người đánh giá';
    const avatarLetter = authorName.charAt(0).toUpperCase();
    const date = review.created_at
        ? new Date(review.created_at).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
        : 'Không rõ ngày';

    const avatar = review.author_avatar_url
        ? `<img src="${review.author_avatar_url}" class="review-avatar-img" alt="${authorName}" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';"><div class="review-avatar" style="display:none;">${avatarLetter}</div>`
        : `<div class="review-avatar">${avatarLetter}</div>`;

    return `
        <article class="review-card">
            ${avatar}
            <div class="review-body">
                <div class="review-header">
                    <span class="review-author">${authorName}</span>
                    ${review.rating !== null && review.rating !== undefined ? `<span class="review-rating">★ ${review.rating}</span>` : ''}
                </div>
                <div class="review-meta">
                    <span>${date}</span>
                    <span>•</span>
                    <span>${review.source.toUpperCase()}</span>
                </div>
                <p class="review-content">${review.content}</p>
            </div>
        </article>
    `;
}

function renderSimilarList(rows) {
    const container = document.getElementById('detailSimilarList');
    if (!container) return;
    if (!rows.length) {
        container.innerHTML = '<p style="color:#666;">Chưa có phim tương tự.</p>';
        return;
    }
    container.innerHTML = rows.map((item) => `
        <a class="similar-item" href="movie.html?id=${item.movie_id}">
            <span class="similar-title">${item.title}</span>
            ${item.score !== null && item.score !== undefined ? `<span class="similar-score">${item.score.toFixed(2)}</span>` : ''}
        </a>
    `).join('');
}

function sentimentIcon(sentiment) {
    if (sentiment === 'positive') return '+';
    if (sentiment === 'negative') return '−';
    return '0';
}

function renderAbsaSection(data) {
    const container = document.getElementById('detailAbsaList');
    if (!container) return;
    if (!data || !data.aspects || !data.aspects.length) {
        container.innerHTML = '<p style="color:#666;">Chưa có dữ liệu ABSA.</p>';
        return;
    }
    container.innerHTML = `
        <div class="absa-grid">
            ${data.aspects.map((a) => `
                <div class="absa-item">
                    <span class="absa-aspect">${a.aspect}</span>
                    <span class="absa-sentiment" data-sentiment="${a.sentiment}">${sentimentIcon(a.sentiment)} ${a.sentiment}</span>
                    <span class="absa-score">${(a.score * 100).toFixed(0)}%</span>
                </div>
            `).join('')}
        </div>
    `;
}

function renderMoviePage(movie) {
    if (!elements.movieDetailContainer) return;
    const posterUrl = getPosterUrl(movie.poster_path);
    const year = movie.release_date ? new Date(movie.release_date).getFullYear() : 'N/A';
    const genres = (movie.genres || []).map((genre) => genre.name).join(', ') || 'Unknown';
    const reviews = movie.reviews || [];

    elements.movieDetailContainer.innerHTML = `
        <div class="movie-detail-layout">
            <div class="detail-poster-column">
                <div class="detail-poster-card">
                    ${posterUrl ? `<img src="${posterUrl}" alt="${movie.title}" class="detail-poster-image">` : '<div class="detail-poster-placeholder">Không có poster</div>'}
                </div>
                <a href="index.html" class="btn-primary detail-back-link">Về trang chủ</a>
            </div>
            <div class="detail-content-column">
                <div class="detail-hero">
                    <h1 class="detail-title">${movie.title}</h1>
                    <div class="detail-meta">
                        <span>${year}</span>
                        <span>•</span>
                        <span>${genres}</span>
                        <span>•</span>
                        <span>${movie.review_count} đánh giá</span>
                        ${movie.average_rating !== null && movie.average_rating !== undefined ? `<span>•</span><span>★ ${movie.average_rating.toFixed(1)}</span>` : ''}
                    </div>
                    <p class="detail-overview">${movie.overview || 'Phim này hiện chưa có mô tả.'}</p>
                </div>
                <section class="similar-section">
                    <h2 class="detail-section-title">Phim tương tự</h2>
                    <p class="detail-hint">
                        Khi mở trang này, hệ thống gọi <code>/movies/${movie.id}/similar</code> để lấy các phim gần nhất từ artifact TF-IDF/Sentence-BERT.
                    </p>
                    <div id="detailSimilarList" class="similar-list">
                        <p style="color:#666;">Đang tải gợi ý...</p>
                    </div>
                </section>
                <section class="absa-section">
                    <h2 class="detail-section-title">Cảm xúc theo khía cạnh (ABSA)</h2>
                    <p class="detail-hint">
                        Cảm xúc theo từng khía cạnh (kịch bản, diễn xuất, hình ảnh, ...), lấy từ endpoint <code>/absa/analyze</code>.
                    </p>
                    <div id="detailAbsaList" class="absa-list">
                        <p style="color:#666;">Đang tải...</p>
                    </div>
                </section>
                <section class="reviews-section">
                    <h2 class="detail-section-title">Đánh giá</h2>
                    ${reviews.length ? `<div class="detail-reviews-list">${reviews.map(createReviewCard).join('')}</div>` : '<div class="loading-container"><p>Chưa có đánh giá cho phim này.</p></div>'}
                </section>
            </div>
        </div>
    `;
}

async function loadMovieDetailPage() {
    if (!elements.movieDetailContainer) return;
    const params = new URLSearchParams(window.location.search);
    const movieId = params.get('id');
    if (!movieId) {
        elements.movieDetailContainer.innerHTML = `
            <div class="loading-container">
                <h2>Không tìm thấy phim</h2>
                <p>Thiếu movie id trong URL.</p>
                <p><a href="index.html" class="btn-primary">Về trang chủ</a></p>
            </div>
        `;
        return;
    }

    try {
        const movie = await getMovieDetails(movieId);
        renderMoviePage(movie);
        try {
            const similar = await getSimilarMovies(movie.id, 8);
            renderSimilarList(similar.results || []);
        } catch (_error) {
            renderSimilarList([]);
        }
        try {
            const absa = await getAbsaAnalysis(movie.id);
            renderAbsaSection(absa);
        } catch (_err) {
            renderAbsaSection(null);
        }
    } catch (error) {
        console.error('Load movie detail failed:', error);
        elements.movieDetailContainer.innerHTML = `
            <div class="loading-container">
                <h2>Không thể tải phim</h2>
                <p>${error.message || 'Vui lòng thử lại sau.'}</p>
                <p><a href="index.html" class="btn-primary">Về trang chủ</a></p>
            </div>
        `;
    }
}

function setupCatalogInteractions() {
    if (elements.recommendationSearchBtn) {
        elements.recommendationSearchBtn.addEventListener('click', () => runRecommendationSearch());
    }
    if (elements.recommendationQuery) {
        elements.recommendationQuery.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') runRecommendationSearch();
        });
    }
    if (elements.recommendationResetBtn) {
        elements.recommendationResetBtn.addEventListener('click', () => {
            if (elements.recommendationQuery) elements.recommendationQuery.value = '';
            state.currentPage = 1;
            loadMovies();
        });
    }
}

function init() {
    if (elements.profileForm) {
        initProfilePage();
        return;
    }
    if (elements.refreshRecommendationsBtn) {
        elements.refreshRecommendationsBtn.addEventListener('click', () => loadRecommendationsForYou());
        loadRecommendationsForYou();
        return;
    }
    if (elements.resultsGrid) {
        applyProfileDefaultsOnCatalog();
        setupCatalogInteractions();
        loadMovies();
        return;
    }
    loadMovieDetailPage();
}

document.addEventListener('DOMContentLoaded', init);
