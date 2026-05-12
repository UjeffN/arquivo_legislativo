/**
 * Transforma um select padrão em um campo pesquisável
 * Para usar: adicionar classe 'select-autocomplete' ao elemento select
 */
(function($) {
    'use strict';

    $.fn.selectAutocomplete = function() {
        return this.each(function() {
            var $select = $(this);
            // Evitar re-inicialização
            if ($select.data('select-autocomplete-initialized')) {
                return;
            }
            $select.data('select-autocomplete-initialized', true);
            var $wrapper = $('<div class="select-autocomplete-wrapper"></div>');
            var $input = $('<input type="text" class="form-control select-autocomplete-input">');
            var $hidden = $('<input type="hidden" class="select-autocomplete-hidden">');
            var $dropdown = $('<div class="select-autocomplete-dropdown" style="display: none;"></div>');

            // Configurar atributos
            $input.attr('placeholder', $select.find('option:first').text() || 'Selecione...');
            $input.attr('id', $select.attr('id') + '_autocomplete');
            $hidden.attr('name', $select.attr('name'));
            $hidden.attr('id', $select.attr('id') + '_hidden');

            // Extrair opções do select
            var options = [];
            $select.find('option').each(function() {
                var $option = $(this);
                if ($option.val()) {
                    options.push({
                        value: $option.val(),
                        text: $option.text(),
                        selected: $option.is(':selected')
                    });
                }
            });

            // Construir dropdown
            options.forEach(function(option) {
                var $item = $('<div class="select-autocomplete-item" data-value="' + option.value + '">' +
                             option.text + '</div>');
                if (option.selected) {
                    $input.val(option.text);
                    $hidden.val(option.value);
                    $item.addClass('selected');
                }
                $dropdown.append($item);
            });

            // Substituir select pelo wrapper
            $select.after($wrapper);
            $wrapper.append($input).append($hidden).append($dropdown);
            $select.hide();
            $select.css('display', 'none !important');
            $select.addClass('select-autocomplete-hidden');

            // Funcionalidade de busca
            $input.on('input', function() {
                var searchTerm = $(this).val().toLowerCase();
                var visibleCount = 0;

                $dropdown.find('.select-autocomplete-item').each(function() {
                    var $item = $(this);
                    var text = $item.text().toLowerCase();

                    if (text.includes(searchTerm)) {
                        $item.show();
                        visibleCount++;
                    } else {
                        $item.hide();
                    }
                });

                // Mostrar/ocultar dropdown
                if (searchTerm.length > 0 || visibleCount > 0) {
                    $dropdown.show();
                } else {
                    $dropdown.hide();
                }

                // Limpar campo hidden se não houver correspondência exata
                var exactMatch = false;
                $dropdown.find('.select-autocomplete-item:visible').each(function() {
                    if ($(this).text().toLowerCase() === searchTerm) {
                        exactMatch = true;
                        return false;
                    }
                });

                if (!exactMatch && searchTerm.length > 0) {
                    $hidden.val('');
                }
            });

            // Seleção de item
            $dropdown.on('click', '.select-autocomplete-item', function() {
                var $item = $(this);
                $input.val($item.text());
                $hidden.val($item.data('value'));

                // Atualizar estado visual
                $dropdown.find('.select-autocomplete-item').removeClass('selected');
                $item.addClass('selected');

                // Atualizar select original
                $select.val($item.data('value'));
                $select.trigger('change');

                $dropdown.hide();
            });

            // Fechar dropdown ao clicar fora
            $(document).on('click', function(e) {
                if (!$(e.target).closest('.select-autocomplete-wrapper').length) {
                    $dropdown.hide();
                }
            });

            // Mostrar dropdown ao focar
            $input.on('focus', function() {
                if ($(this).val().length === 0) {
                    $dropdown.find('.select-autocomplete-item').show();
                    $dropdown.show();
                } else {
                    $(this).trigger('input');
                }
            });

            // Navegação por teclado
            $input.on('keydown', function(e) {
                var $visibleItems = $dropdown.find('.select-autocomplete-item:visible');
                var $selected = $visibleItems.filter('.selected');
                var $newSelected;

                switch(e.keyCode) {
                    case 38: // Up
                        e.preventDefault();
                        if ($selected.length === 0) {
                            $newSelected = $visibleItems.last();
                        } else {
                            $newSelected = $selected.prevAll(':visible:first');
                            if ($newSelected.length === 0) {
                                $newSelected = $visibleItems.last();
                            }
                        }
                        $visibleItems.removeClass('selected');
                        $newSelected.addClass('selected');
                        break;

                    case 40: // Down
                        e.preventDefault();
                        if ($selected.length === 0) {
                            $newSelected = $visibleItems.first();
                        } else {
                            $newSelected = $selected.nextAll(':visible:first');
                            if ($newSelected.length === 0) {
                                $newSelected = $visibleItems.first();
                            }
                        }
                        $visibleItems.removeClass('selected');
                        $newSelected.addClass('selected');
                        break;

                    case 13: // Enter
                        e.preventDefault();
                        if ($selected.length > 0) {
                            $selected.click();
                        }
                        break;

                    case 27: // Escape
                        $dropdown.hide();
                        break;
                }
            });
        });
    };

    // Inicializar automaticamente
    $(function() {
        $('.select-autocomplete').selectAutocomplete();
    });

})(typeof django !== 'undefined' && django.jQuery ? django.jQuery : jQuery);
