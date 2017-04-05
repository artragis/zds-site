(function ($, undefined) {
    var $tribunes = $(".tribune");
    $tribunes.on("click", ".unpick-action", function () {
       var $button = $(this);
       var $parent = $button.parent(".tribune");
       var csrfmiddlewaretoken = $("input[name=csrfmiddlewaretoken]").val();
       $.post($button.attr("data-url"), {
           operation: $button.attr("data-operation"),
           csrfmiddlewaretoken:csrfmiddlewaretoken
       }).done(function () {
           $parent.parent().remove($parent);
       });
    });
})(jQuery);
