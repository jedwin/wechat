
function imageInit(){
    // 用于游戏界面中图片的点击放大预览
    var imgList = [];
    // 获取容器内所有的img元素
    var imgObjs = $(".game_img");
    // 遍历img元素
    for(var i=0; i<imgObjs.length; i++){
      imgList.push(imgObjs.eq(i).attr('src'));
      // 给img元素添加点击事件
      imgObjs.eq(i).click(function(){
        var imgUrl = $(this).attr('src');
        wx.previewImage({
          current: imgUrl , // 当前显示图片的http链接
          urls: imgList     // 需要预览的图片http链接列表
        });
      });
    }
  }

function option_click(option){
    // 点击选项的操作
    var $loadingToast = $('#loadingToast');
    if ($loadingToast.css('display') != 'none') return;
    $loadingToast.fadeIn(100);
    setTimeout(function () {
        $loadingToast.fadeOut(100);
    }, 2000);
    $my_form = $('#form_question');
    $my_form.append('<input type="hidden" name="cmd" value="'+option+'">');
    $my_form.submit();
}