(function () {
    const provinceSelect = document.querySelector('[data-province-select]');
    const citySelect = document.querySelector('[data-city-select]');
    const cityDataElement = document.getElementById('address-city-data');

    if (!provinceSelect || !citySelect || !cityDataElement) return;

    const citiesByProvince = JSON.parse(cityDataElement.textContent);

    function updateCities(keepSelection) {
        const previousCity = keepSelection ? citySelect.value : '';
        const cities = citiesByProvince[provinceSelect.value] || [];
        citySelect.replaceChildren(new Option('شهر را انتخاب کنید', ''));

        cities.forEach((city) => citySelect.add(new Option(city, city)));
        citySelect.disabled = cities.length === 0;

        if (cities.includes(previousCity)) {
            citySelect.value = previousCity;
        }
    }

    provinceSelect.addEventListener('change', () => updateCities(false));
    updateCities(true);
})();
