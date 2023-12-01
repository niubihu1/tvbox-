var rule = {
    title:'s 野格影视',
    host:'http://shadiao8.com/',
    // homeUrl:'/',
    url:'/vod/show/id/fyclass/page/fypage/.html',
    // http://shadiao8.com/vod/show/id/23/page/2.html
    searchUrl:'/vod/search/page/fypage/wd/**.html',
    // http://shadiao8.com/vod/search/page/fypage/wd/**.html
    searchable:2,//是否启用全局搜索,
    quickSearch:1,//是否启用快速搜索,
    filterable:0,//是否启用分类筛选,
    headers:{//网站的请求头,完整支持所有的,常带ua和cookies
        'User-Agent':'MOBILE_UA',
        // "Cookie": "searchneed=ok"
    },
    class_name:'电影&电视剧&综艺&动漫&国产剧&泰剧&台剧&韩剧&日剧',
    class_url:'1&2&5&3&15&23&20&18&21',
    play_parse:true,
    lazy:'',
    limit:6,
    推荐:'*',
    //推荐:'.module-item;.module-item-cover&&.module-item-pic;a&&title;.lazyloaded&&data-src;.module-item-text&&Text;a&&href',
    double:true, // 推荐内容是否双层定位
    //一级:'.module-list&&.module-item-pic;a&&title;.lazyloaded&&data-src;.module-item-text&&Text;a&&href',
    一级:'.hl-list-wrap li;a&&title;.hl-lazy&&data-original;.remarks&&Text;a&&href',
    二级:{"title":"h2.hl-dc-title hl-data-menu&&Text;.video-info-aux&&Text","img":".lazyload&&data-src","desc":".hl-col-xs-12 hl-col-sm-4:eq(-1)&&Text;.hl-col-xs-12 hl-col-sm-4:eq(-3)&&Text;.hl-col-xs-12 hl-col-sm-4:eq(-2)&&Text;.hl-col-xs-12 hl-col-sm-4:eq(1)&&.hl-col-xs-12 hl-col-sm-4&&Text;.video-info-items:eq(0)&&.video-info-item.video-info-actor&&Text","content":".hl-col-xs-12 .blurb&&Text","tabs":".hl-from-list","lists":".hl-plays-list:eq(#id) a"},
    搜索:'.hl-list-wrap;.hl-item-title&&Text;.hl-item-thumb.hl-lazy&&data-original;.hl-pic-text&&Text;a&&href',
 }
