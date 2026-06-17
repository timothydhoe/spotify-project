const formModel = {
  title: "Check-in formulier REM",
  description: "Bedankt om deel te nemen aan dit onderzoek. Vul dit formulier in bij de start en het einde van je check-in. Alle antwoorden worden anoniem verwerkt.",
  sections: [
    {
      id: "greeting",
      title: "Begroeting",
      type: "static_text",
      content: "Welkom! Vul dit formulier in bij de start en het einde van je check-in."
    },
    {
      id: "general_info",
      title: "Algemene informatie",
      fields: [
        { id: "participant_code", label: "Deelnemerscode", type: "text", required: true },
        {
          id: "playlist",
          label: "Welke playlist luisterde je?",
          type: "multiple_choice",
          required: true,
          options: ["Calm", "Neutral", "Energy"]
        },
        { id: "date", label: "Welke dag deed je een check-in?", type: "date", required: true },
        { id: "start_time", label: "Starttijd?", type: "time", required: true },
        { id: "end_time", label: "Eindtijd?", type: "time", required: true }
      ]
    },
    {
      id: "start_feeling",
      title: "Gevoel bij start van Check-in",
      fields: [
        {
          id: "start_feeling_type",
          label: "Welk gevoel had je?",
          type: "multiple_choice",
          required: true,
          options: ["Moe of ongemotiveerd", "Neutraal", "Gestresseerd of gespannen", "Andere..."]
        },
        {
          id: "start_score",
          label: "Score je gevoel op een schaal van 1–10",
          type: "multiple_choice",
          required: true,
          options: ["1","2","3","4","5","6","7","8","9","10"]
        }
      ]
    },
    {
      id: "end_feeling",
      title: "Gevoel bij eind van Check-in",
      fields: [
        {
          id: "end_feeling_type",
          label: "Welk gevoel had je?",
          type: "multiple_choice",
          required: true,
          options: ["Moe of ongemotiveerd", "Neutraal", "Gestresseerd of gespannen", "Andere..."]
        },
        {
          id: "end_score",
          label: "Score je gevoel op een schaal van 1–10",
          type: "multiple_choice",
          required: true,
          options: ["1","2","3","4","5","6","7","8","9","10"]
        }
      ]
    },
    {
      id: "reflection",
      title: "Reflectie",
      fields: [
        { id: "influential_songs", label: "Waren er specifieke nummers in de playlist die je gevoel beïnvloed hebben?", type: "paragraph", required: false },
        { id: "noticed_moments", label: "Waren er specifieke momenten in de playlist die je opvielen?", type: "paragraph", required: false }
      ]
    },
    {
      id: "other_info",
      title: "Overige informatie",
      fields: [
        {
          id: "location",
          label: "Waar heb je geluisterd?",
          type: "multiple_choice",
          required: true,
          options: ["Thuis", "Anders..."]
        },
        {
          id: "full_playlist",
          label: "Heb je de volledige playlist kunnen luisteren?",
          type: "multiple_choice",
          required: true,
          options: ["Ja", "Onderbroken", "Nee"]
        }
      ]
    },
    {
      id: "consent",
      title: "Toestemming",
      type: "static_text",
      content:
        "Ik geef toestemming dat mijn data anoniem wordt verwerkt.\n" +
        "De onderzoeksgegevens worden bewaard tot 15/06/2027.\n" +
        "Uw contactgegevens worden gescheiden bewaard en vernietigd binnen 1 maand na afloop van het onderzoek.\n" +
        "U kunt uw gegevens laten verwijderen tot 15/05/2026. Na deze datum zijn gegevens geanonimiseerd en niet meer traceerbaar.",
      fields: [
        {
          id: "consent_checkbox",
          label: "Ik bevestig dat ik de informatie hierboven heb gelezen en ga akkoord.",
          type: "checkbox",
          required: true
        }
      ]
    }
  ]
};


function createREMCheckInForm() {

  const form = FormApp.create(formModel.title);
  form.setDescription(formModel.description);

  formModel.sections.forEach(section => {

    // Sectie header
    form.addPageBreakItem().setTitle(section.title);

    // Statische tekst
    if (section.type === "static_text" && section.content) {
      form.addParagraphTextItem()
        .setTitle("Informatie")
        .setHelpText(section.content);
    }

    // Vragen
    if (section.fields) {
      section.fields.forEach(field => {
        let item;

        switch (field.type) {

          case "text":
            item = form.addTextItem().setTitle(field.label);
            break;

          case "paragraph":
            item = form.addParagraphTextItem().setTitle(field.label);
            break;

          case "multiple_choice":
            item = form.addMultipleChoiceItem().setTitle(field.label);
            item.setChoices(field.options.map(opt => item.createChoice(opt)));
            break;

          case "checkbox":
            item = form.addCheckboxItem().setTitle(field.label);
            item.setChoices([item.createChoice(field.label)]);
            break;

          case "date":
            item = form.addDateItem().setTitle(field.label);
            break;

          case "time":
            item = form.addTimeItem().setTitle(field.label);
            break;
        }

        if (field.required) item.setRequired(true);
      });
    }
  });

  Logger.log("Nieuw REM Check-in formulier aangemaakt: " + form.getEditUrl());
}