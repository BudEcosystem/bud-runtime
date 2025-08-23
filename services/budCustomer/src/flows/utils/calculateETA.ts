export const calculateEta = (eta: string | number, setEta?: any) => {
  if (eta) {
    let time = "Calculating...";
    try {
      const hours = Math.floor(Number(eta) / 60);
      const minutes = Number(eta) % 60;
      time = `${hours} hours ${minutes} minutes`;
    } catch (error) {
      time = "Calculating...";
    }
    if (time === "Invalid Date") {
      time = "Calculating...";
    }

    if (setEta) {
      setEta(time);
    }
    return time;
  }
};


export const calculateEtaInDays = (eta: string | number) => {
  if (eta) {
    let time = "Calculating...";
    try {
      const days = Math.floor(((Number(eta) / 60) / 60) / 24);
      time = `${days > 0 ?  days > 1 ? `${days} days` : `${days} day` : `${days} day`}`;
    } catch (error) {
      time = "Calculating...";
    }
    if (time === "Invalid Date") {
      time = "Calculating...";
    }

    return time;
  }
}

export const calculateEtaInHoursAndMinutesExcludeDays = (eta: string | number) => {
  if (eta) {
    let time = "Calculating...";
    try {
      // seconds to hours
      const hours = Math.floor(Number(eta) / 60) % 24;
      const minutes = Number(eta) % 60;
      time = `${hours} hours ${minutes} minutes`;
    } catch (error) {
      time = "Calculating...";
    }
    if (time === "Invalid Date") {
      time = "Calculating...";
    }

    return time;
  }
}
