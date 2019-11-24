/*
 * Allow the user to compare two commits
 */
(function(document, $, undefined){
  "use strict";

  function hideMoveButton() {
    /* TODO : REMOVE this and update the selectlist with js */
    /* because the list is not updated */
    $(".simple-move-button").hide();
  }

  function sendMoveAction(evt) {
    hideMoveButton();

    // sending
    const $item = $(evt.item);
    const $from = $(evt.from);
    const movingMethod = (($prev) => {
      const path = ((tree) => {
        $item.parents("[data-children-type]:not([data-pk])").each((n, parent) => {
          tree.push($(parent).attr("data-slug"));
        });
        tree = tree.reverse();
        if (tree.length > 0) {
          tree.push("");
        }
        return tree.join("/");
      })([]);

      if ($prev[0]) {
        return "after:" + path + $prev.attr("data-slug");
      } else {
        return "first:" + path;
      }
    })($item.prev());

    const isExtract = ($from.attr("data-children-type") === "extract");
    const isPart = (!!$item.children("[data-children-type=container]")[0]);

    const pk = $item.parents("[data-pk]").attr("data-pk");
    const slug = $item.attr("data-slug");

    const form = {
      // new 
      "moving_method": movingMethod,
      // old
      "container_slug": $from.attr("data-slug"),
      "first_level_slug": (isExtract) ? $from.parents("[data-children-type]").attr("data-slug") : undefined,
      // current
      "child_slug": slug,
      "pk": pk,
      // csrf
      "csrfmiddlewaretoken": $("input[name=csrfmiddlewaretoken]").val()
    };

    $.post("/contenus/deplacer/", form);

    // modifie les URLs
    const path = ((tree) => {
      $item.parents("[data-children-type]").each((n, parent) => {
        tree.push($(parent).attr("data-slug"));
      });
      tree = tree.reverse();
      return tree.join("/");
    })([]);

    $item.find("> .actions-title a.edit").attr("href", `/contenus/editer-conteneur/${pk}/${path}/${slug}/`);
    $("form#delete-" + slug).attr("action", `/contenus/supprimer/${pk}/${path}/${slug}/`);
    $item.find("> *:first-child > a, [data-children-type] > [data-slug] a").each(function () {
      const $parents = $(this).parents("[data-slug]");
      const type = $(this).parents("[data-children-type]").attr("data-children-type");
      const mySlug = $parents.attr("data-slug");

      let fullpath = (slug !== mySlug) ? `${path}/${slug}` : path; 

      if (type === "extract") {
        fullpath += (isPart) ? "/" + $parents.eq(1).attr("data-slug") : "";
        $(this).attr("href", `/contenus/${pk}/${fullpath}/#${$parents.eq(0).index()+1}-${mySlug}`);
      } else if (type === "container") {
        $(this).attr("href", `/contenus/${pk}/${fullpath}/${mySlug}`);
      } else {
        console.warn("type inattendu.", type);
      }
    });
    $item.find(".simple-create-button")
      .attr("href", `/contenus/nouvelle-section/${pk}/${path}/${slug}/`);
  }

  function canDrop($item, $to, $from) {
    // TODO : [BACK] Change slug if we have the same.
    const filter = "[data-slug=" + $item.attr("data-slug") + "]";
    if ($to.children(filter).length >= (1 + $to.is($from))) {
      return false;
    }
    return true;
  }

  $(document).ready(function() {
    $("ol[data-children-type=extract]").sortable({
      group: "extract",
      handle: "a",
      filter: function (pointer, dragged) {
        return $(dragged).is(".simple-create-button");
      },
      onMove: (evt) => {
        const $item = $(evt.dragged);
        const $to = $(evt.related).parent();
        const $from = $(evt.dragged).parent();

        if (!canDrop($item, $to, $from)) {
          return false;
        }

        if (!$to.is($from)) {
          // Element is dragged into the list from another list
          if ($from.parent().is(".article-containers > .article-part")) { // is: chapter > extract
            $item.find("> h4 > a").unwrap().wrap("<h3></h3>");
          } else { // is: part > chapter > extract 
            $item.find("> h3 > a").unwrap().wrap("<h4></h4>");
          }
        }

        if ($(evt.related).is(".simple-create-button")) {
          return -1;
        }
      },
      onEnd: sendMoveAction
    });

    $("*[data-children-type=container]").sortable({
      group: "container",
      handle: ["h2", "h3 a"],
      filter: function (pointer, dragged) {
        return $(dragged).is(".simple-create-part");
      },
      onMove: (evt) => {
        const $item = $(evt.dragged);
        const $to = $(evt.related).parent();
        const $from = $(evt.dragged).parent();

        if (!canDrop($item, $to, $from)) {
          return false;
        }

        if (!$to.is($from)) {
          // Element is dragged into the list from another list
          if ($to.is("section")) { // is: chapter > extract
            $item.find("> h3 > a").unwrap().wrap("<h2></h2>");
            $item.find("ol h4 > a").unwrap().wrap("<h3></h3>");

            if ($item.find(".simple-create-part")[0]) {
              $item.children(".article-containers").show();
              $item.children("ol.summary-part").hide();
            }
          } else { // is: part > chapter > extract 
            $item.find("> h2 > a").unwrap().wrap("<h3></h3>");
            $item.find("ol h3 > a").unwrap().wrap("<h4></h4>");

            if ($item.find(".simple-create-part")[0]) {
              $item.children(".article-containers").hide();
              $item.append(
                `<ol class="summary-part" data-children-type="extract">
                  <li class="simple-create-button">
                    <a class="btn btn-grey">Ajouter une section</a>
                  </li>
                </ol>`
              );
            }
          }
        }

        if ($(evt.related).is(".simple-create-part")) {
          return -1;
        }
      },
      onEnd: sendMoveAction
    });
  });
})(document, jQuery);
