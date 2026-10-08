window.bookingDatePicker = function (schedule, serviceDurations) {
    const now = new Date();
    const todayString = [
        now.getFullYear(),
        String(now.getMonth() + 1).padStart(2, "0"),
        String(now.getDate()).padStart(2, "0"),
    ].join("-");

    return {
        step: "date",
        displayedMonth: new Date(now.getFullYear(), now.getMonth(), 1),
        selectedDate: "",
        selectedTime: "",
        selectedServiceId: "",
        error: "",
        todayString,
        schedule,
        serviceDurations,
        weekdays: ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"],

        get timeOptions() {
            if (this.schedule !== null && !this.selectedDate) return [];

            const date = this.selectedDate
                ? new Date(`${this.selectedDate}T00:00:00`)
                : null;
            const periods = this.schedule === null
                ? [["00:00", "24:00"]]
                : (this.schedule[String(date.getDay())] || []);
            const duration = Number(this.serviceDurations[this.selectedServiceId]) || 30;
            const available = new Set();

            for (const [start, end] of periods) {
                const startMinutes = this.toMinutes(start);
                const endMinutes = this.toMinutes(end);
                for (let minutes = startMinutes; minutes + duration <= endMinutes; minutes += 30) {
                    const hours = String(Math.floor(minutes / 60)).padStart(2, "0");
                    const remainder = String(minutes % 60).padStart(2, "0");
                    available.add(`${hours}:${remainder}`);
                }
            }

            return [...available].sort();
        },

        get monthLabel() {
            return this.displayedMonth.toLocaleDateString("pt-BR", {
                month: "long",
                year: "numeric",
            });
        },

        get calendarCells() {
            const year = this.displayedMonth.getFullYear();
            const month = this.displayedMonth.getMonth();
            const offset = new Date(year, month, 1).getDay();
            const daysInMonth = new Date(year, month + 1, 0).getDate();

            return Array.from({ length: 42 }, (_, index) => {
                const day = index - offset + 1;
                if (day < 1 || day > daysInMonth) {
                    return { key: index, day: "", date: "" };
                }

                const date = new Date(year, month, day);
                const dateString = [
                    date.getFullYear(),
                    String(date.getMonth() + 1).padStart(2, "0"),
                    String(date.getDate()).padStart(2, "0"),
                ].join("-");

                return { key: index, day, date: dateString };
            });
        },

        get previousMonthDisabled() {
            const current = new Date();
            return this.displayedMonth.getFullYear() === current.getFullYear()
                && this.displayedMonth.getMonth() === current.getMonth();
        },

        get selectedDateLabel() {
            if (!this.selectedDate) return "";
            return new Date(`${this.selectedDate}T00:00:00`).toLocaleDateString("pt-BR", {
                weekday: "long",
                day: "numeric",
                month: "long",
                year: "numeric",
            });
        },

        get dateTimeValue() {
            return this.selectedDate && this.selectedTime
                ? `${this.selectedDate}T${this.selectedTime}`
                : "";
        },

        toMinutes(value) {
            const [hours, minutes] = value.split(":").map(Number);
            return hours * 60 + minutes;
        },

        changeMonth(offset) {
            this.displayedMonth = new Date(
                this.displayedMonth.getFullYear(),
                this.displayedMonth.getMonth() + offset,
                1,
            );
        },

        selectDate(date) {
            if (!date || date < this.todayString) return;
            this.selectedDate = date;
            if (!this.timeOptions.includes(this.selectedTime)) this.selectedTime = "";
            this.error = "";
            this.step = "time";
        },
    };
};