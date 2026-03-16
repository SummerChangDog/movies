// DOM元素
const movieInput = document.getElementById('movieInput');
const searchBtn = document.getElementById('searchBtn');
const loader = document.getElementById('loader');
const error = document.getElementById('error');
const errorText = document.getElementById('errorText');
const results = document.getElementById('results');

// 电影信息元素
const moviePoster = document.getElementById('moviePoster');
const movieTitle = document.getElementById('movieTitle');
const movieYear = document.getElementById('movieYear');
const movieGenre = document.getElementById('movieGenre');
const movieDirector = document.getElementById('movieDirector');
const movieActors = document.getElementById('movieActors');
const moviePlot = document.getElementById('moviePlot');

// 评分元素
const doubanScore = document.getElementById('doubanScore');
const doubanVotes = document.getElementById('doubanVotes');
const doubanStars = document.getElementById('doubanStars');
const doubanDistribution = document.getElementById('doubanDistribution');
const doubanDistBars = document.getElementById('doubanDistBars');

const imdbScore = document.getElementById('imdbScore');
const imdbVotes = document.getElementById('imdbVotes');
const imdbStars = document.getElementById('imdbStars');
const imdbDistribution = document.getElementById('imdbDistribution');
const imdbDistBars = document.getElementById('imdbDistBars');

const rtCriticScore = document.getElementById('rtCriticScore');
const rtAudienceScore = document.getElementById('rtAudienceScore');
const rtCriticIcon = document.getElementById('rtCriticIcon');
const rtAudienceIcon = document.getElementById('rtAudienceIcon');
const rtDistribution = document.getElementById('rtDistribution');
const rtDistBars = document.getElementById('rtDistBars');

// 事件监听
searchBtn.addEventListener('click', handleSearch);
movieInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        handleSearch();
    }
});

// 搜索处理函数
async function handleSearch() {
    let movieName = movieInput.value.trim();
    
    if (!movieName) {
        showError('请输入电影名称');
        return;
    }
    
    // 验证输入 - 移除或转义特殊字符
    // 允许中文、英文、数字、空格和一些基本符号
    const validPattern = /^[\u4e00-\u9fa5a-zA-Z0-9\s\-\':,.!?&]+$/;
    if (!validPattern.test(movieName)) {
        showError('电影名称包含不支持的字符，请使用中文、英文、数字或常见符号');
        return;
    }
    
    // 限制输入长度
    if (movieName.length > 100) {
        showError('电影名称过长，请输入100个字符以内');
        return;
    }
    
    // 重置状态
    hideError();
    hideResults();
    showLoader();
    
    try {
        // 调用后端API
        console.log('正在搜索电影:', movieName);
        
        const response = await fetch('/api/search', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ movie_name: movieName })
        });
        
        console.log('响应状态:', response.status, response.statusText);
        
        const data = await response.json();
        console.log('响应数据:', data);
        
        if (!response.ok) {
            throw new Error(data.error || `搜索失败 (${response.status})`);
        }
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        // 显示结果
        displayResults(data);
        
    } catch (err) {
        showError(err.message || '搜索出错，请稍后重试');
    } finally {
        hideLoader();
    }
}

// 显示搜索结果
function displayResults(data) {
    // 基本信息
    moviePoster.src = data.poster || 'static/images/no-poster.jpg';
    moviePoster.alt = data.title || '';
    movieTitle.textContent = data.title || '未知电影';
    movieYear.textContent = data.year ? `(${data.year})` : '';
    movieGenre.textContent = data.genre || '未知类型';
    movieDirector.innerHTML = data.director ? `<strong>导演：</strong>${data.director}` : '';
    movieActors.innerHTML = data.actors ? `<strong>主演：</strong>${data.actors}` : '';
    moviePlot.textContent = data.plot || '暂无剧情简介';
    
    // 豆瓣评分
    if (data.douban) {
        doubanScore.textContent = data.douban.score || '-';
        doubanVotes.textContent = formatNumber(data.douban.votes) || '-';
        doubanStars.innerHTML = createStars(data.douban.score);
        // 评分分布
        if (data.douban.rating_distribution && Object.keys(data.douban.rating_distribution).length > 0) {
            renderDoubanDistribution(data.douban.rating_distribution);
        } else {
            doubanDistribution.classList.add('hidden');
        }
    } else {
        doubanScore.textContent = '-';
        doubanVotes.textContent = '-';
        doubanStars.innerHTML = '';
        doubanDistribution.classList.add('hidden');

        // 若未配置豆瓣 Cookie，在评分区域显示友好提示
        if (!data._douban_cookie_configured) {
            doubanVotes.innerHTML =
                '<span class="douban-tip" title="在 .env 中配置 DOUBAN_COOKIE_BID 和 DOUBAN_COOKIE_DBCL2 即可启用">' +
                '⚠️ 需配置 Cookie' +
                '</span>';
        }
    }
    
    // IMDb评分
    if (data.imdb) {
        imdbScore.textContent = data.imdb.score || '-';
        imdbVotes.textContent = formatNumber(data.imdb.votes) || '-';
        imdbStars.innerHTML = createStars(data.imdb.score);
        // 评分分布
        if (data.imdb.rating_distribution && Object.keys(data.imdb.rating_distribution).length > 0) {
            renderIMDbDistribution(data.imdb.rating_distribution);
        } else {
            imdbDistribution.classList.add('hidden');
        }
    } else {
        imdbScore.textContent = '-';
        imdbVotes.textContent = '-';
        imdbStars.innerHTML = '';
        imdbDistribution.classList.add('hidden');
    }
    
    // 烂番茄评分
    if (data.rottenTomatoes) {
        rtCriticScore.textContent = data.rottenTomatoes.critic ? `${data.rottenTomatoes.critic}%` : '-%';
        rtAudienceScore.textContent = data.rottenTomatoes.audience ? `${data.rottenTomatoes.audience}%` : '-%';
        
        // 更新图标颜色
        updateRTIcon(rtCriticIcon, data.rottenTomatoes.critic);
        updateRTIcon(rtAudienceIcon, data.rottenTomatoes.audience);

        // 评分分布
        if (data.rottenTomatoes.rating_distribution &&
            Object.keys(data.rottenTomatoes.rating_distribution).length > 0) {
            renderRTDistribution(data.rottenTomatoes.rating_distribution);
        } else {
            rtDistribution.classList.add('hidden');
        }
    } else {
        rtCriticScore.textContent = '-%';
        rtAudienceScore.textContent = '-%';
        rtDistribution.classList.add('hidden');
    }
    
    // 雷达图
    const doubanDist = (data.douban && data.douban.rating_distribution) ? data.douban.rating_distribution : null;
    const imdbDist   = (data.imdb   && data.imdb.rating_distribution)   ? data.imdb.rating_distribution   : null;
    renderRadarChart(normalizeDouban(doubanDist), normalizeIMDb(imdbDist));

    showResults();
}

// 创建星级评分
function createStars(score) {
    if (!score || score === '-') return '';
    
    const rating = parseFloat(score);
    const fullStars = Math.floor(rating / 2);
    const hasHalf = (rating / 2) % 1 >= 0.5;
    const emptyStars = 5 - fullStars - (hasHalf ? 1 : 0);
    
    let stars = '';
    
    // 填充满星
    for (let i = 0; i < fullStars; i++) {
        stars += '<span class="star filled">★</span>';
    }
    
    // 半星
    if (hasHalf) {
        stars += '<span class="star half">★</span>';
    }
    
    // 空星
    for (let i = 0; i < emptyStars; i++) {
        stars += '<span class="star">★</span>';
    }
    
    return stars;
}

// 更新烂番茄图标
function updateRTIcon(icon, score) {
    if (!score || score === '-') {
        icon.style.color = '#ccc';
        return;
    }
    
    const percentage = parseInt(score);
    if (percentage >= 60) {
        icon.style.color = '#FA320A'; // 新鲜
    } else {
        icon.style.color = '#0AC855'; // 腐烂
    }
}

// 格式化数字
function formatNumber(num) {
    if (!num) return null;
    
    if (num >= 10000) {
        return (num / 10000).toFixed(1) + '万';
    }
    
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

// UI控制函数
function showLoader() {
    loader.classList.remove('hidden');
}

function hideLoader() {
    loader.classList.add('hidden');
}

function showError(message) {
    errorText.textContent = message;
    error.classList.remove('hidden');
}

function hideError() {
    error.classList.add('hidden');
}

function showResults() {
    results.classList.remove('hidden');
}

function hideResults() {
    results.classList.add('hidden');
}

// ---- 评分分布渲染 ----

/**
 * 渲染豆瓣评分分布（5星→1星，百分比格式）
 * dist 格式: { '5星': 45.2, '4星': 32.1, '3星': 15.0, '2星': 5.0, '1星': 2.7 }
 */
function renderDoubanDistribution(dist) {
    // 固定顺序：5星 → 1星
    const order = ['5星', '4星', '3星', '2星', '1星'];
    const maxPct = Math.max(...order.map(k => dist[k] || 0));

    doubanDistBars.innerHTML = '';
    order.forEach(label => {
        const pct = dist[label] || 0;
        const barWidth = maxPct > 0 ? (pct / maxPct * 100).toFixed(1) : 0;
        const row = document.createElement('div');
        row.className = 'dist-row';
        row.innerHTML = `
            <span class="dist-label">${label}</span>
            <div class="dist-bar-track">
                <div class="dist-bar-fill" style="width: 0%"
                     data-target="${barWidth}%"></div>
            </div>
            <span class="dist-percent">${pct.toFixed(1)}%</span>
        `;
        doubanDistBars.appendChild(row);
    });

    doubanDistribution.classList.remove('hidden');
    // 延迟触发动画
    requestAnimationFrame(() => {
        doubanDistBars.querySelectorAll('.dist-bar-fill').forEach(el => {
            el.style.width = el.dataset.target;
        });
    });
}

/**
 * 渲染 IMDb 评分分布（10星→1星，含票数和百分比）
 * dist 格式: { '10': {votes: N, percent: P}, '9': {...}, ... }
 */
function renderIMDbDistribution(dist) {
    const maxPct = Math.max(...Object.values(dist).map(v => v.percent || 0));

    imdbDistBars.innerHTML = '';
    // 从10星到1星倒序显示
    for (let star = 10; star >= 1; star--) {
        const key = String(star);
        const info = dist[key] || { votes: 0, percent: 0 };
        const pct = info.percent || 0;
        const barWidth = maxPct > 0 ? (pct / maxPct * 100).toFixed(1) : 0;

        const row = document.createElement('div');
        row.className = 'dist-row';
        row.innerHTML = `
            <span class="dist-label">${star}★</span>
            <div class="dist-bar-track">
                <div class="dist-bar-fill" style="width: 0%"
                     data-target="${barWidth}%"></div>
            </div>
            <span class="dist-percent">${pct.toFixed(1)}%</span>
        `;
        imdbDistBars.appendChild(row);
    }

    imdbDistribution.classList.remove('hidden');
    // 延迟触发动画
    requestAnimationFrame(() => {
        imdbDistBars.querySelectorAll('.dist-bar-fill').forEach(el => {
            el.style.width = el.dataset.target;
        });
    });
}

/**
 * 渲染烂番茄新鲜度分布
 * dist 格式: {
 *   critics:  { fresh: 88.0, rotten: 12.0 },
 *   audience: { liked: 71.0, disliked: 29.0 }
 * }
 */
function renderRTDistribution(dist) {
    rtDistBars.innerHTML = '';

    // 专业评分部分
    if (dist.critics) {
        const freshPct  = dist.critics.fresh  || 0;
        const rottenPct = dist.critics.rotten || 0;

        const rows = [
            { label: '🍅 新鲜', pct: freshPct,  cls: 'dist-bar-fill rt-fresh'  },
            { label: '🤢 腐烂', pct: rottenPct, cls: 'dist-bar-fill rt-rotten' },
        ];
        // 分组标题
        const groupTitle = document.createElement('div');
        groupTitle.className = 'dist-group-title';
        groupTitle.textContent = '专业影评';
        rtDistBars.appendChild(groupTitle);

        rows.forEach(({ label, pct, cls }) => {
            const row = document.createElement('div');
            row.className = 'dist-row';
            row.innerHTML = `
                <span class="dist-label">${label}</span>
                <div class="dist-bar-track">
                    <div class="${cls}" style="width: 0%" data-target="${pct}%"></div>
                </div>
                <span class="dist-percent">${pct.toFixed(1)}%</span>
            `;
            rtDistBars.appendChild(row);
        });
    }

    // 观众评分部分
    if (dist.audience) {
        const likedPct    = dist.audience.liked    || 0;
        const dislikedPct = dist.audience.disliked || 0;

        const rows = [
            { label: '👍 喜欢',   pct: likedPct,    cls: 'dist-bar-fill rt-liked'    },
            { label: '👎 不喜欢', pct: dislikedPct, cls: 'dist-bar-fill rt-disliked' },
        ];
        const groupTitle = document.createElement('div');
        groupTitle.className = 'dist-group-title';
        groupTitle.textContent = '观众评分';
        rtDistBars.appendChild(groupTitle);

        rows.forEach(({ label, pct, cls }) => {
            const row = document.createElement('div');
            row.className = 'dist-row';
            row.innerHTML = `
                <span class="dist-label">${label}</span>
                <div class="dist-bar-track">
                    <div class="${cls}" style="width: 0%" data-target="${pct}%"></div>
                </div>
                <span class="dist-percent">${pct.toFixed(1)}%</span>
            `;
            rtDistBars.appendChild(row);
        });
    }

    rtDistribution.classList.remove('hidden');
    // 延迟触发动画
    requestAnimationFrame(() => {
        rtDistBars.querySelectorAll('[data-target]').forEach(el => {
            el.style.width = el.dataset.target;
        });
    });
}

// ---- 雷达图 ----

let radarChartInstance = null;  // 保存 Chart 实例，下次搜索时销毁重建

/**
 * 将豆瓣评分分布（5维度）归一化为百分比数组
 * dist: { '5星': 45.2, '4星': 32.1, '3星': 15.0, '2星': 5.0, '1星': 2.7 }
 * 返回: [极度热爱%, 喜爱认可%, 中立态度%, 失望批评%, 强烈抵制%]
 */
function normalizeDouban(dist) {
    if (!dist) return null;
    const raw = [
        dist['5星'] || 0,   // 极度热爱
        dist['4星'] || 0,   // 喜爱认可
        dist['3星'] || 0,   // 中立态度
        dist['2星'] || 0,   // 失望批评
        dist['1星'] || 0    // 强烈抵制
    ];
    const total = raw.reduce((a, b) => a + b, 0);
    if (total === 0) return null;
    return raw.map(v => parseFloat((v / total * 100).toFixed(2)));
}

/**
 * 将 IMDb 评分分布（10段）归一化为5维度百分比数组
 * dist: { '10': {votes, percent}, '9': {...}, ... }
 * 分组规则：9-10→极度热爱, 7-8→喜爱认可, 5-6→中立态度, 3-4→失望批评, 1-2→强烈抵制
 * 返回: [极度热爱%, 喜爱认可%, 中立态度%, 失望批评%, 强烈抵制%]
 */
function normalizeIMDb(dist) {
    if (!dist) return null;
    const get = (key) => (dist[String(key)] ? (dist[String(key)].percent || 0) : 0);
    const raw = [
        get(10) + get(9),   // 极度热爱
        get(8)  + get(7),   // 喜爱认可
        get(6)  + get(5),   // 中立态度
        get(4)  + get(3),   // 失望批评
        get(2)  + get(1)    // 强烈抵制
    ];
    const total = raw.reduce((a, b) => a + b, 0);
    if (total === 0) return null;
    return raw.map(v => parseFloat((v / total * 100).toFixed(2)));
}

/**
 * 渲染雷达图
 * @param {number[]|null} doubanData  5维百分比数组（归一化后）
 * @param {number[]|null} imdbData    5维百分比数组（归一化后）
 */
function renderRadarChart(doubanData, imdbData) {
    const section = document.getElementById('radarSection');

    // 两个平台都没有数据时隐藏整个区块
    if (!doubanData && !imdbData) {
        section.classList.add('hidden');
        return;
    }

    section.classList.remove('hidden');

    // 销毁旧图表实例
    if (radarChartInstance) {
        radarChartInstance.destroy();
        radarChartInstance = null;
    }

    const labels = ['极度热爱', '喜爱认可', '中立态度', '失望批评', '强烈抵制'];
    const datasets = [];

    if (doubanData) {
        datasets.push({
            label: '豆瓣',
            data: doubanData,
            backgroundColor: 'rgba(0, 172, 99, 0.15)',
            borderColor: 'rgba(0, 172, 99, 0.9)',
            borderWidth: 2.5,
            pointBackgroundColor: 'rgba(0, 172, 99, 1)',
            pointBorderColor: '#fff',
            pointHoverBackgroundColor: '#fff',
            pointHoverBorderColor: 'rgba(0, 172, 99, 1)',
            pointRadius: 4,
            pointHoverRadius: 6
        });
    }

    if (imdbData) {
        datasets.push({
            label: 'IMDb',
            data: imdbData,
            backgroundColor: 'rgba(245, 197, 24, 0.15)',
            borderColor: 'rgba(245, 197, 24, 0.95)',
            borderWidth: 2.5,
            pointBackgroundColor: 'rgba(245, 197, 24, 1)',
            pointBorderColor: '#fff',
            pointHoverBackgroundColor: '#fff',
            pointHoverBorderColor: 'rgba(245, 197, 24, 1)',
            pointRadius: 4,
            pointHoverRadius: 6
        });
    }

    const ctx = document.getElementById('radarChart').getContext('2d');
    radarChartInstance = new Chart(ctx, {
        type: 'radar',
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            animation: {
                duration: 800,
                easing: 'easeInOutQuart'
            },
            scales: {
                r: {
                    beginAtZero: true,
                    min: 0,
                    ticks: {
                        stepSize: 10,
                        callback: (v) => v + '%',
                        font: { size: 10 },
                        color: '#888',
                        backdropColor: 'transparent'
                    },
                    grid: {
                        color: 'rgba(0,0,0,0.08)'
                    },
                    angleLines: {
                        color: 'rgba(0,0,0,0.12)'
                    },
                    pointLabels: {
                        font: { size: 13, weight: '600' },
                        color: '#333'
                    }
                }
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        font: { size: 13 },
                        usePointStyle: true,
                        padding: 20
                    }
                },
                tooltip: {
                    callbacks: {
                        label: (ctx) => ` ${ctx.dataset.label}: ${ctx.raw.toFixed(1)}%`
                    }
                }
            }
        }
    });
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    movieInput.focus();
});
